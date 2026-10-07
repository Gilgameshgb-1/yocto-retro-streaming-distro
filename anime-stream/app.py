"""Anime library, search and player — the third web app on the retro box.

Sits alongside the game launcher (retro.pi:5000) and the movie player
(stream.pi:5001) on its own port, with its own nginx vhost and systemd unit,
following the same pattern as those two.

Playback has two destinations, as the movie app does:
  * the TV, via mpv on the Pi's DRM/KMS output, driven over JSON IPC
  * the phone itself, via HTTP range requests to an HTML5 <video>
"""

import os
import re

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file, send_from_directory)

import config
import downloader
import library
import nyaa
import player
import subtitles as subs_mod

app = Flask(__name__, template_folder='templates', static_folder='static')

MIME_TYPES = {
    '.mp4':  'video/mp4',
    '.mkv':  'video/x-matroska',
    '.webm': 'video/webm',
    '.avi':  'video/x-msvideo',
    '.m4v':  'video/mp4',
    '.mov':  'video/quicktime',
}

# What is currently loaded on the TV, so we can save its position before
# switching files and so the UI can show "resume" vs "start".
_now_playing = {'path': None}


# ─── Library ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html',
                           series=library.scan(include_episodes=False),
                           downloads_enabled=downloader.available())


@app.route('/api/library')
def api_library():
    return jsonify(library.scan(include_episodes=False))


@app.route('/api/series/<slug>')
def api_series(slug):
    series = library.get_series(slug)
    if series is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(series)


@app.route('/poster/<slug>')
def poster(slug):
    path = library.poster_path(library.slugify(slug))
    if not os.path.isfile(path):
        return '', 404
    return send_file(path, mimetype='image/jpeg', max_age=86400)


@app.route('/api/meta/<slug>')
def api_meta(slug):
    """Fetch AniList metadata for a series on demand.

    Downloads trigger this automatically; this route covers series copied in by
    hand, and a forced refresh when the parsed title matched the wrong show.
    """
    series = library.get_series(slug)
    if series is None:
        return jsonify({'error': 'not found'}), 404
    title = request.args.get('title') or series['folder_title']
    force = request.args.get('force') == '1'
    meta = library.backfill_metadata(series['slug'], title, force=force)
    if meta is None:
        return jsonify({'found': False})
    return jsonify({'found': True, 'meta': meta})


# ─── Nyaa search and downloads ─────────────────────────────────────────────

@app.route('/api/series/<slug>/rename', methods=['POST'])
def api_rename_series(slug):
    """Rename a series folder. Parsed names are often wrong."""
    body = request.get_json(silent=True) or {}
    result = library.rename_series(slug, body.get('name', ''))
    if not result.get('ok'):
        return jsonify(result), 400
    # The folder is the lookup key, so refresh metadata under the new name.
    library.backfill_metadata(result['slug'], result['folder'], force=True)
    return jsonify(result)


def _in_use(paths):
    """Why these library files can't be deleted right now, or None.

    Anything a running download writes to, or that is playing on the TV,
    is off limits; cancelling the download (with "delete partial files")
    is the way to remove a release that is still coming in.
    """
    folders, files, unknown = downloader.busy_paths()
    for full in paths:
        if full in files or any(full.startswith(f + os.sep) for f in unknown):
            return ('Still downloading. Cancel it in the downloads list, and tick '
                    '"delete the partial files" to remove it.')
    playing = _now_playing.get('path')
    if playing and player.is_running():
        playing_full = library.resolve(playing)
        if playing_full in paths:
            return 'Playing on the TV right now. Stop it first.'
    return None


@app.route('/api/episode/delete', methods=['POST'])
def api_delete_episode():
    body = request.get_json(silent=True) or {}
    rel = body.get('file') or ''
    full = library.resolve(rel)
    if not full or not os.path.isfile(full):
        return jsonify({'ok': False, 'error': 'episode not found'}), 404
    reason = _in_use({full})
    if reason:
        return jsonify({'ok': False, 'error': reason}), 409
    folders, _files, _unknown = downloader.busy_paths()
    result = library.delete_episode(rel, keep_folders=folders)
    return jsonify(result), (200 if result.get('ok') else 404)


@app.route('/api/series/<slug>/delete', methods=['POST'])
def api_delete_series(slug):
    series = library.get_series(slug)
    if series is None:
        return jsonify({'ok': False, 'error': 'series not found'}), 404
    paths = {library.resolve(ep['path']) for ep in series['episodes']}
    reason = _in_use(paths)
    if reason:
        return jsonify({'ok': False, 'error': reason}), 409
    # A download still starting into this folder has no file list yet.
    folder_abs = library.resolve(series['folder'])
    folders, _files, _unknown = downloader.busy_paths()
    if folder_abs in folders:
        return jsonify({'ok': False, 'error': 'A download is still running into this '
                        'series. Cancel it in the downloads list first.'}), 409
    return jsonify(library.delete_series(slug))


@app.route('/api/search')
def api_search():
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'error': 'No search term provided'}), 400

    def flag(name):
        return request.args.get(name) in ('1', 'true', 'yes')

    batch_param = request.args.get('batch', 'any')
    batch = {'only': True, 'none': False}.get(batch_param)

    try:
        results = nyaa.search(
            query,
            category=request.args.get('category', 'english'),
            filter_mode='trusted' if flag('trusted') else 'none',
            page=int(request.args.get('page', 1) or 1),
        )
    except Exception as exc:                     # noqa: BLE001 - network/XML
        return jsonify({'error': f'Could not reach nyaa.si: {exc}'}), 502

    total = len(results)
    max_gb = request.args.get('max_gb', type=float)
    min_gb = request.args.get('min_gb', type=float)
    results = nyaa.apply_filters(
        results,
        resolution=request.args.get('resolution') or None,
        min_seeders=request.args.get('min_seeders', default=1, type=int),
        max_size_bytes=int(max_gb * 1024 ** 3) if max_gb else None,
        min_size_bytes=int(min_gb * 1024 ** 3) if min_gb else None,
        batch=batch,
        trusted_only=flag('trusted'),
    )

    for item in results:
        item['series_folder'] = downloader.suggest_series_name(item['raw_title'])
        item['size_warning'] = item['size_bytes'] > config.WARN_SIZE_BYTES
        # No video episode is a few MB — those listings are subtitle packs.
        item['likely_subs_only'] = (item['size_bytes'] > 0
                                    and item['size_bytes'] < 60 * 1024 ** 2)

    # Nyaa serves a newest-first window and ignores its own sort params, so
    # ordering is applied here over the fetched page.
    sort_key = request.args.get('sort', nyaa.DEFAULT_SORT)
    results = nyaa.sort_results(results, sort_key)

    return jsonify({
        'results':       results,
        'sort':          sort_key if sort_key in nyaa.SORT_KEYS else nyaa.DEFAULT_SORT,
        'shown':         len(results),
        'total':         total,
        'warn_size_gb':  config.WARN_SIZE_BYTES // 1024 ** 3,
    })


@app.route('/api/resolve-title')
def api_resolve_title():
    """Canonical title suggestions for a parsed release name.

    Scene and batch releases carry episode titles and encoder tags that no
    parser can reliably strip ("DAN DA DAN Clash Space Kaiju vs Giant Robot"),
    so rather than guess a folder name we offer AniList's canonical titles and
    let the download dialog confirm one.
    """
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'suggestions': []})

    import anilist
    meta = anilist.lookup_fuzzy(query)
    suggestions = []
    if meta:
        for key in ('title_english', 'title_romaji'):
            value = (meta.get(key) or '').strip()
            if value and value not in suggestions:
                suggestions.append(value)
    return jsonify({
        'suggestions': [downloader.safe_folder_name(s) for s in suggestions],
        'score':       (meta or {}).get('score'),
        'year':        (meta or {}).get('year'),
    })


@app.route('/api/download', methods=['POST'])
def api_download():
    if not downloader.available():
        return jsonify({
            'error': 'libtorrent is not installed — install python3-libtorrent '
                     'to enable downloads. Search and playback still work.'
        }), 503

    body = request.get_json(silent=True) or {}
    magnet = body.get('magnet')
    if not magnet:
        return jsonify({'error': 'No magnet link provided'}), 400

    release = body.get('release') or 'Unknown release'
    series = body.get('series') or downloader.suggest_series_name(release)

    try:
        dl_id = downloader.start_download(
            magnet,
            series_title=series,
            release_title=release,
            poster_url=body.get('poster'),
            sequential=bool(body.get('sequential')),
        )
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503

    return jsonify({'id': dl_id, 'series': series, 'state': 'started'})


@app.route('/api/downloads')
def api_downloads():
    dl_id = request.args.get('id', type=int)
    if dl_id is not None:
        status = downloader.get_status(dl_id)
        return jsonify(status if status else {'error': 'not found'})
    return jsonify(downloader.get_status())


@app.route('/api/downloads/cancel', methods=['POST'])
def api_download_cancel():
    body = request.get_json(silent=True) or {}
    dl_id = body.get('id')
    if dl_id is None:
        return jsonify({'error': 'No id provided'}), 400
    return jsonify(downloader.cancel(int(dl_id),
                                    delete_files=bool(body.get('delete_files'))))


@app.route('/api/downloads/pause', methods=['POST'])
def api_download_pause():
    body = request.get_json(silent=True) or {}
    dl_id = body.get('id')
    if dl_id is None:
        return jsonify({'error': 'No id provided'}), 400
    return jsonify(downloader.set_paused(int(dl_id), bool(body.get('paused'))))


@app.route('/api/downloads/clear', methods=['POST'])
def api_downloads_clear():
    return jsonify({'remaining': downloader.clear_finished()})


# ─── TV playback ───────────────────────────────────────────────────────────

def _save_current_position():
    """Persist the position of whatever is on the TV right now."""
    current = _now_playing.get('path')
    if not current:
        return
    state = player.status()
    if state and state.get('position'):
        library.set_progress(current, state['position'], state.get('duration') or 0)


@app.route('/api/play')
def api_play():
    rel = request.args.get('file', '')
    full = library.resolve(rel)
    if not full or not os.path.isfile(full):
        return jsonify({'error': 'file not found'}), 404

    # Switching episodes should not lose where we were in the last one.
    if _now_playing.get('path') and _now_playing['path'] != rel:
        _save_current_position()

    entry = library.load_resume().get(rel) or {}
    start = entry.get('pos') or 0
    if start and entry.get('dur') and start / entry['dur'] >= library.WATCHED_FRACTION:
        start = 0                                 # finished last time, restart

    if not player.load(full, start_seconds=start):
        return jsonify({
            'error': f'Could not start the player ({config.MPV_EXE}). '
                     'Is mpv installed and on PATH?'
        }), 503

    _now_playing['path'] = rel
    return jsonify({'playing': rel, 'resumed_at': start})


@app.route('/api/status')
def api_status():
    state = player.status()
    if state is None:
        return jsonify({'playing': False}), 200
    state['playing'] = True
    state['file'] = _now_playing.get('path')
    return jsonify(state)


@app.route('/files/<action>')
def api_files(action):
    actions = {
        'play-pause': lambda: player.cycle_pause(),
        'backward':   lambda: player.seek(-10),
        'forward':    lambda: player.seek(10),
        'back-85':    lambda: player.seek(-85),
        'skip-85':    lambda: player.seek(85),      # anime OP is ~90s
    }
    if action not in actions:
        return jsonify({'error': 'unknown action'}), 400
    actions[action]()
    return jsonify({'ok': True})


@app.route('/api/seek')
def api_seek():
    pct = request.args.get('pct', type=float)
    if pct is None:
        return jsonify({'error': 'pct required'}), 400
    player.seek(max(0, min(100, pct)), 'absolute-percent')
    return jsonify({'ok': True})


@app.route('/api/tracks')
def api_tracks():
    """Audio and subtitle tracks embedded in the file on the TV."""
    return jsonify(player.tracks())


@app.route('/api/track', methods=['POST'])
def api_set_track():
    body = request.get_json(silent=True) or {}
    kind = body.get('kind')
    track_id = body.get('id')
    if kind not in ('audio', 'sub') or track_id is None:
        return jsonify({'error': 'kind must be audio|sub, id required'}), 400
    player.set_track(kind, track_id)
    return jsonify({'ok': True})


@app.route('/api/stop')
def api_stop():
    _save_current_position()
    player.stop()
    _now_playing['path'] = None
    return jsonify({'ok': True})


@app.route('/api/quit')
def api_quit():
    _save_current_position()
    player.quit_player()
    _now_playing['path'] = None
    return jsonify({'ok': True})


# ─── Phone streaming ───────────────────────────────────────────────────────

@app.route('/stream/<path:rel>')
def stream(rel):
    full = library.resolve(rel)
    if not full or not os.path.isfile(full):
        return 'not found', 404

    mime = MIME_TYPES.get(os.path.splitext(full)[1].lower(), 'application/octet-stream')
    size = os.path.getsize(full)
    range_header = request.headers.get('Range')

    if not range_header:
        response = send_file(full, mimetype=mime, conditional=True)
        response.headers['Accept-Ranges'] = 'bytes'
        return response

    match = re.search(r'bytes=(\d*)-(\d*)', range_header)
    if not match or not match.group(1):
        response = send_file(full, mimetype=mime, conditional=True)
        response.headers['Accept-Ranges'] = 'bytes'
        return response

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else size - 1
    end = min(end, size - 1)
    if start > end:
        return Response(status=416, headers={'Content-Range': f'bytes */{size}'})
    length = end - start + 1

    def chunks():
        with open(full, 'rb') as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(262144, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block

    return Response(chunks(), 206, headers={
        'Content-Range':  f'bytes {start}-{end}/{size}',
        'Accept-Ranges':  'bytes',
        'Content-Length': str(length),
        'Content-Type':   mime,
    })


@app.route('/api/subtitles')
def api_subtitles():
    """Sidecar subtitle tracks for an episode, for the in-browser player.

    Subtitles muxed inside the mkv are not listed here — a browser cannot read
    them without a remux. Those are available on TV playback via /api/tracks,
    and the UI says so rather than silently offering nothing.
    """
    rel = request.args.get('file', '')
    full = library.resolve(rel)
    if not full:
        return jsonify([])
    for series in library.scan():
        for episode in series['episodes']:
            if episode['path'] == rel:
                return jsonify([
                    {'label': s['label'], 'url': '/subtitles/' + s['path']}
                    for s in episode['subs']
                ])
    return jsonify([])


@app.route('/subtitles/<path:rel>')
def serve_subtitle(rel):
    full = library.resolve(rel)
    if not full or not os.path.isfile(full):
        return 'not found', 404
    with open(full, 'r', encoding='utf-8', errors='replace') as handle:
        vtt = subs_mod.to_vtt(handle.read(), os.path.basename(full))
    return Response(vtt, mimetype='text/vtt')


# ─── Watch progress ────────────────────────────────────────────────────────

@app.route('/api/resume')
def api_resume_get():
    rel = request.args.get('file', '')
    entry = library.load_resume().get(rel) or {}
    return jsonify({'pos': entry.get('pos', 0), 'dur': entry.get('dur', 0)})


@app.route('/api/resume', methods=['POST'])
def api_resume_save():
    body = request.get_json(silent=True) or {}
    rel = body.get('file')
    if not rel or library.resolve(rel) is None:
        return jsonify({'error': 'bad path'}), 400
    entry = library.set_progress(rel, body.get('pos', 0), body.get('dur', 0))
    return jsonify(entry)


@app.route('/api/watched', methods=['POST'])
def api_mark_watched():
    """Flip an episode between watched and unwatched by hand."""
    body = request.get_json(silent=True) or {}
    rel = body.get('file')
    if not rel or library.resolve(rel) is None:
        return jsonify({'error': 'bad path'}), 400

    data = library.load_resume()
    entry = data.get(rel, {})
    duration = float(entry.get('dur') or body.get('dur') or 0)

    if body.get('watched'):
        # Without a known runtime, use a nominal one so the ratio reads as done.
        duration = duration or 1440.0
        entry = {'pos': duration, 'dur': duration}
    else:
        entry = {'pos': 0, 'dur': duration}

    data[rel] = entry
    library.save_resume(data)
    return jsonify(entry)


@app.route('/api/health')
def api_health():
    return jsonify({
        'anime_dir':        config.ANIME_DIR,
        'anime_dir_exists': os.path.isdir(config.ANIME_DIR),
        'series_count':     len(library.scan(include_episodes=False)),
        'downloads':        downloader.available(),
        'libtorrent_error': downloader.LIBTORRENT_ERROR,
        'storage_problem':  config.storage_problem(),
        'player_exe':       config.MPV_EXE,
        'player_running':   player.is_running(),
        'mpv_ipc':          config.MPV_IPC_PATH,
        'on_pi':            config.ON_PI,
    })


if __name__ == '__main__':
    config.ensure_dirs()
    print(f'  anime library : {config.ANIME_DIR}')
    print(f'  player        : {config.MPV_EXE}  (ipc {config.MPV_IPC_PATH})')
    print(f'  downloads     : {"enabled" if downloader.available() else "DISABLED (no libtorrent)"}')
    print(f'  listening on  : http://{config.HOST}:{config.PORT}\n')
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
