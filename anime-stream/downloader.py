"""Torrent downloads into the anime library.

Differences from the movie app's downloader, all driven by how anime releases
actually arrive:

* One shared libtorrent session. The movie app builds a fresh session per
  download, so two concurrent downloads both try to bind port 6881 and one
  loses. Here the session is created once, lazily.

* No file flattening. A batch torrent unpacks into its own folder, sometimes
  with a Fonts/ subdirectory beside the episodes. The library scanner walks
  recursively, so there is nothing to rearrange — and not moving files means
  not scattering a release's fonts or breaking its sidecar subtitle pairing.

* Downloads land in ANIME_DIR/<series>/ with the series name taken from the
  parsed release title, so every episode of a show accumulates in one folder.

libtorrent is imported defensively: without it, search and playback still work
and only downloading is unavailable, which keeps the UI testable on a machine
that has no python3-libtorrent.
"""

import os
import re
import shutil
import threading
import time

import config
import library
import release_parser

try:
    import libtorrent as lt
    LIBTORRENT_ERROR = None
except ImportError as exc:                       # pragma: no cover
    lt = None
    LIBTORRENT_ERROR = str(exc)

_downloads = {}
_counter = [0]
_lock = threading.Lock()
_session = [None]

_INVALID = r'[\\/:*?"<>|]'


def available():
    return lt is not None


def safe_folder_name(title):
    """Make a release title usable as a directory name.

    Colons become spaced hyphens rather than bare ones, so an AniList
    title like "Frieren: Beyond Journey's End" reads as
    "Frieren - Beyond Journey's End" instead of "Frieren- Beyond ...".
    """
    name = re.sub(r'\s*:\s*', ' - ', title or '')
    name = re.sub(_INVALID, '-', name)
    name = re.sub(r'\s+', ' ', name).strip(' .-')
    return name or 'Unsorted'


def _get_session():
    if _session[0] is None:
        _session[0] = lt.session({
            'listen_interfaces': '0.0.0.0:6881',
            'alert_mask': lt.alert.category_t.error_notification,
        })
    return _session[0]


def start_download(magnet, series_title, release_title=None, poster_url=None,
                   sequential=False):
    """Queue a magnet for download. Returns the download id.

    `series_title` decides the folder, so all episodes of a show land together
    even when each release has a differently decorated filename.
    """
    if lt is None:
        raise RuntimeError(f'libtorrent unavailable: {LIBTORRENT_ERROR}')
    problem = config.storage_problem()
    if problem:
        raise RuntimeError(problem)

    folder = safe_folder_name(series_title)
    save_path = os.path.join(config.ANIME_DIR, folder)
    folder_existed = os.path.isdir(save_path)
    os.makedirs(save_path, exist_ok=True)

    with _lock:
        _counter[0] += 1
        dl_id = _counter[0]

    _downloads[dl_id] = {
        'id':             dl_id,
        'series':         series_title,
        'folder':         folder,
        'release':        release_title or series_title,
        'save_path':      save_path,
        'progress':       0.0,
        'download_rate':  0,
        'upload_rate':    0,
        'num_peers':      0,
        'num_seeds':      0,
        'total_bytes':    0,
        'done_bytes':     0,
        'eta_seconds':    None,
        'state':          'starting',
        'paused':         False,
        'error':          None,
        'started_at':     int(time.time()),
        'folder_existed': folder_existed,
        'slug':           library.slugify(folder),
        'detail':         _release_detail(release_title),
    }

    thread = threading.Thread(
        target=_worker,
        args=(dl_id, magnet, save_path, series_title, poster_url, sequential),
        daemon=True,
    )
    thread.start()
    return dl_id


def _release_detail(release_title):
    """What a release holds, short enough for the downloads list."""
    parsed = release_parser.parse(release_title or '')
    if parsed['ep_start'] is not None:
        return f"Episodes {parsed['ep_start']}–{parsed['ep_end']}"
    if parsed['is_batch']:
        return f"Season {parsed['season']} batch" if parsed['season'] else 'Batch'
    episode = parsed['episode']
    if isinstance(episode, int):
        return f'Ep {episode:02d}'
    return f'Ep {episode}' if episode is not None else ''


def set_paused(dl_id, paused):
    """Pause or resume one download.

    The torrent is taken off auto-management before pausing, otherwise the
    session's queue would quietly resume it a moment later.
    """
    entry = _downloads.get(dl_id)
    if entry is None:
        return {'ok': False, 'error': 'Download not found'}
    handle = entry.get('handle')
    if handle is None:
        return {'ok': False, 'error': 'Download has not started yet'}
    if paused:
        handle.unset_flags(lt.torrent_flags.auto_managed)
        handle.pause()
    else:
        handle.resume()
    entry['paused'] = bool(paused)
    return {'ok': True, 'paused': entry['paused']}


def _worker(dl_id, magnet, save_path, series_title, poster_url, sequential):
    handle = None
    try:
        session = _get_session()
        params = lt.parse_magnet_uri(magnet)
        params.save_path = save_path
        handle = session.add_torrent(params)

        with _lock:
            entry = _downloads.get(dl_id)
            if entry is not None:
                entry['handle'] = handle

        if sequential:
            handle.set_sequential_download(True)

        _downloads[dl_id]['state'] = 'downloading'

        # Metadata and cover art can be fetched while the swarm warms up.
        threading.Thread(
            target=_backfill_meta, args=(series_title, poster_url), daemon=True
        ).start()

        while True:
            if dl_id not in _downloads:
                session.remove_torrent(handle)
                return

            if config.storage_problem():
                # The SSD vanished mid-download; /movies is now a folder on
                # the SD card. Stop before libtorrent starts filling that.
                session.remove_torrent(handle)
                _downloads[dl_id].update({
                    'state':         'error',
                    'error':         'SSD disappeared, download stopped. Add the '
                                     'same release again once it is back; '
                                     'finished pieces are kept.',
                    'download_rate': 0,
                    'eta_seconds':   None,
                })
                return

            status = handle.status()
            rate = status.download_rate
            remaining = max(0, status.total_wanted - status.total_wanted_done)

            _downloads[dl_id].update({
                'progress':      round(status.progress * 100, 1),
                'download_rate': rate,
                'upload_rate':   status.upload_rate,
                'num_peers':     status.num_peers,
                'num_seeds':     status.num_seeds,
                'total_bytes':   status.total_wanted,
                'done_bytes':    status.total_wanted_done,
                'eta_seconds':   int(remaining / rate) if rate > 0 else None,
                'state':         str(status.state),
            })

            if status.is_seeding or status.progress >= 1.0:
                break
            time.sleep(1)

        _downloads[dl_id].update({
            'progress':      100.0,
            'state':         'finished',
            'download_rate': 0,
            'upload_rate':   0,
            'eta_seconds':   0,
        })

        # Stop seeding; this is a media box, not a seedbox.
        session.remove_torrent(handle)

        # Now that filenames exist on disk, metadata can use the real title.
        _backfill_meta(series_title, poster_url)

    except Exception as exc:                     # noqa: BLE001 - surfaced to UI
        if dl_id in _downloads:
            _downloads[dl_id]['state'] = 'error'
            _downloads[dl_id]['error'] = str(exc)


def _backfill_meta(series_title, poster_url):
    """Cache AniList metadata plus a cover image for this series."""
    slug = library.slugify(safe_folder_name(series_title))
    try:
        meta = library.backfill_metadata(slug, series_title)
        if meta is None and poster_url:
            import anilist
            anilist.fetch_cover(poster_url, library.poster_path(slug))
    except Exception:                            # noqa: BLE001 - best effort
        pass


def get_status(dl_id=None):
    def clean(entry):
        return {k: v for k, v in entry.items() if k != 'handle'}
    if dl_id is not None:
        entry = _downloads.get(dl_id)
        return clean(entry) if entry else None
    return [clean(e) for e in _downloads.values()]


def cancel(dl_id, delete_files=False):
    """Stop a download. With `delete_files`, also remove what it wrote.

    Only the files this torrent reported are deleted, and the series folder
    itself only if this download created it and left it empty — so cancelling
    one episode never takes out a series you already had.
    """
    entry = _downloads.pop(dl_id, None)
    if entry is None:
        return {'cancelled': False, 'error': 'Download not found'}

    handle = entry.get('handle')
    removed = []

    if delete_files and handle is not None:
        try:
            info = handle.torrent_file()
            if info is not None:
                for index in range(info.num_files()):
                    rel = info.files().file_path(index)
                    target = os.path.join(entry['save_path'], rel)
                    if os.path.isfile(target):
                        os.remove(target)
                        removed.append(rel)
                    for partial in (target + '.parts', target + '.part'):
                        if os.path.isfile(partial):
                            os.remove(partial)
        except Exception:                        # noqa: BLE001 - best effort
            pass

        # libtorrent also leaves a .parts file next to the save path.
        try:
            for name in os.listdir(entry['save_path']):
                if name.endswith('.parts'):
                    os.remove(os.path.join(entry['save_path'], name))
        except OSError:
            pass

        if not entry.get('folder_existed'):
            try:
                if not os.listdir(entry['save_path']):
                    shutil.rmtree(entry['save_path'])
            except OSError:
                pass

    try:
        if handle is not None and _session[0] is not None:
            _session[0].remove_torrent(handle)
    except Exception:                            # noqa: BLE001
        pass

    return {'cancelled': True, 'release': entry['release'], 'removed': len(removed)}


def busy_paths():
    """What running downloads are writing to, so the library won't delete it.

    Returns (folders, files, unknown_folders) as sets of absolute paths.
    `unknown_folders` holds downloads still fetching metadata: their file
    names aren't known yet, so anything in those folders counts as busy.
    """
    folders, files, unknown = set(), set(), set()
    for entry in list(_downloads.values()):
        if entry['state'] in ('finished', 'error'):
            continue
        folder = os.path.abspath(entry['save_path'])
        folders.add(folder)
        info = None
        try:
            handle = entry.get('handle')
            info = handle.torrent_file() if handle is not None else None
        except Exception:                        # noqa: BLE001 - best effort
            info = None
        if info is None:
            unknown.add(folder)
            continue
        storage = info.files()
        for index in range(info.num_files()):
            files.add(os.path.abspath(os.path.join(folder, storage.file_path(index))))
    return folders, files, unknown


def clear_finished():
    """Drop finished and errored entries from the active list."""
    for dl_id in [k for k, v in _downloads.items()
                  if v['state'] in ('finished', 'error')]:
        _downloads.pop(dl_id, None)
    return len(_downloads)


def suggest_series_name(release_title):
    """The series folder we'd use for a given nyaa release title."""
    parsed = release_parser.parse(release_title)
    return safe_folder_name(parsed['title'] or release_title)
