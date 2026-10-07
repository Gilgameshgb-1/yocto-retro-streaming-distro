"""Scan the anime directory into a series -> seasons -> episodes tree.

The movie library is flat: one folder, one film. Anime is not — a single
torrent is often a whole cour, so the on-disk layout is

    ANIME_DIR/<series folder>/**/<episode files>

Each top-level directory is one series. Episode numbers come from
release_parser applied to the filename, so a batch that unpacks into a messy
nested folder still sorts correctly.

Posters and AniList metadata are cached under STATE_DIR keyed by series slug,
which keeps the media folders pure and means a virtual series (loose files
dropped straight into ANIME_DIR) is handled by the same code path.
"""

import json
import os
import re
import shutil
import time

import anilist
import config
import release_parser

POSTER_DIR = None          # resolved lazily so tests can point config elsewhere


def _poster_dir():
    global POSTER_DIR
    POSTER_DIR = os.path.join(config.STATE_DIR, 'posters')
    os.makedirs(POSTER_DIR, exist_ok=True)
    return POSTER_DIR


def slugify(name):
    slug = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    return slug or 'untitled'


def poster_path(slug):
    return os.path.join(_poster_dir(), f'{slug}.jpg')


def meta_path(slug):
    return os.path.join(_poster_dir(), f'{slug}.json')


# ─── Watch progress ────────────────────────────────────────────────────────
# Keyed by path relative to ANIME_DIR, so the library stays portable if it
# moves between a laptop and the Pi's NVMe.

def load_resume():
    try:
        with open(config.RESUME_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    # Tolerate a bare number, which is how the movie app stores progress.
    out = {}
    for key, value in (raw or {}).items():
        if isinstance(value, dict):
            out[key] = value
        else:
            try:
                out[key] = {'pos': float(value), 'dur': 0}
            except (TypeError, ValueError):
                continue
    return out


def save_resume(data):
    config.ensure_dirs()
    tmp = config.RESUME_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, config.RESUME_FILE)


def set_progress(rel_path, pos, dur=0):
    data = load_resume()
    entry = data.get(rel_path, {})
    entry['pos'] = float(pos or 0)
    if dur:
        entry['dur'] = float(dur)
    entry['updated'] = int(time.time())
    data[rel_path] = entry
    save_resume(data)
    return entry


WATCHED_FRACTION = 0.9     # past this much of the runtime, call it watched


def _progress_fields(entry):
    pos = float((entry or {}).get('pos') or 0)
    dur = float((entry or {}).get('dur') or 0)
    pct = (pos / dur * 100) if dur > 0 else 0
    watched = bool(dur > 0 and pos / dur >= WATCHED_FRACTION)
    return {
        'resume_time':  pos,
        'duration':     dur,
        'progress_pct': round(pct, 1),
        'watched':      watched,
        'started':      pos > 30 and not watched,
        'updated':      int((entry or {}).get('updated') or 0),
    }


# ─── Scanning ──────────────────────────────────────────────────────────────

def _episode_sort_key(ep):
    """Order by season then episode, floating unnumbered files to the end."""
    return (
        ep['season'] if ep['season'] is not None else 1,
        0 if ep['episode'] is not None else 1,
        ep['episode'] if ep['episode'] is not None else 0,
        ep['filename'].lower(),
    )


def _find_sidecar_subs(video_abs):
    """Sidecar subtitle files sitting next to (and named like) the video."""
    folder = os.path.dirname(video_abs)
    stem = os.path.splitext(os.path.basename(video_abs))[0].lower()
    subs = []
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return subs
    for name in entries:
        lower = name.lower()
        if not lower.endswith(config.SUB_EXTS):
            continue
        sub_stem = os.path.splitext(lower)[0]
        # Either an exact stem match or a language-suffixed variant, where the
        # suffix ("...episode.eng.srt") becomes the menu label.
        if sub_stem == stem or sub_stem.startswith(stem):
            suffix = os.path.splitext(name)[0][len(stem):].strip(' .-_[]()')
            subs.append({
                'label': suffix or 'Subtitles',
                'path':  os.path.relpath(os.path.join(folder, name), config.ANIME_DIR),
            })
    return subs


def _build_episode(abs_path, resume):
    rel = os.path.relpath(abs_path, config.ANIME_DIR)
    filename = os.path.basename(abs_path)
    parsed = release_parser.parse(filename)

    try:
        size = os.path.getsize(abs_path)
    except OSError:
        size = 0

    if parsed['episode'] is not None:
        label = f"Episode {parsed['episode']}"
    else:
        label = os.path.splitext(filename)[0]

    episode = {
        'path':       rel,
        'filename':   filename,
        'season':     parsed['season'],
        'episode':    parsed['episode'],
        'label':      label,
        'resolution': parsed['resolution'],
        'codec':      parsed['codec'],
        # The parser strips bit depth as title noise, so it is read here.
        'ten_bit':    bool(re.search(r'\b10[\s\-]?bits?\b|\bhi10p?\b', filename, re.I)),
        'source':     parsed['source'],
        'audio':      parsed['audio'],
        'group':      parsed['group'],
        'hdr':        parsed['hdr'],
        'dual_audio': parsed['dual_audio'],
        'size_bytes': size,
        'subs':       _find_sidecar_subs(abs_path),
        'warning':    release_parser.playback_warning(
                          parsed['resolution'], parsed['codec']),
    }
    episode.update(_progress_fields(resume.get(rel)))
    return episode


def _load_cached_meta(slug):
    try:
        with open(meta_path(slug), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_meta(slug, meta):
    _poster_dir()
    tmp = meta_path(slug) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    os.replace(tmp, meta_path(slug))


def _series_from_episodes(folder_name, episodes, resume):
    slug = slugify(folder_name)
    episodes.sort(key=_episode_sort_key)

    seasons = {}
    for ep in episodes:
        seasons.setdefault(ep['season'] if ep['season'] is not None else 1, []).append(ep)

    watched = sum(1 for e in episodes if e['watched'])
    meta = _load_cached_meta(slug) or {}

    # First episode that isn't finished — what a "Continue" button should open.
    nxt = next((e for e in episodes if not e['watched']), None)
    in_progress = next((e for e in episodes if e['started']), None)

    display = meta.get('title_english') or meta.get('title_romaji') or folder_name
    fully_watched = bool(episodes) and watched == len(episodes)

    return {
        'slug':           slug,
        'folder':         folder_name,
        'title':          display,
        'folder_title':   folder_name,
        'has_poster':     os.path.isfile(poster_path(slug)),
        'meta':           meta,
        'seasons':        {str(k): v for k, v in sorted(seasons.items())},
        'season_numbers': sorted(seasons.keys()),
        'episodes':       episodes,
        'episode_count':  len(episodes),
        'watched_count':  watched,
        'total_bytes':    sum(e['size_bytes'] for e in episodes),
        'resume':         in_progress or nxt,
        'next_episode':   nxt,
        'fully_watched':  fully_watched,
        # Started but not finished: drives the "Watching" filter and the
        # "Continue watching" card, which picks the most recent last_watched.
        'in_progress':    not fully_watched and (watched > 0 or in_progress is not None),
        'last_watched':   max((e['updated'] for e in episodes), default=0),
    }


def scan(include_episodes=True):
    """Walk ANIME_DIR and return a list of series dicts, newest first."""
    config.ensure_dirs()
    resume = load_resume()
    series_map = {}
    loose = []

    try:
        entries = sorted(os.listdir(config.ANIME_DIR))
    except OSError:
        return []

    for entry in entries:
        abs_entry = os.path.join(config.ANIME_DIR, entry)

        if os.path.isdir(abs_entry):
            found = []
            for root, _dirs, files in os.walk(abs_entry):
                for name in sorted(files):
                    if name.lower().endswith(config.VIDEO_EXTS):
                        found.append(_build_episode(os.path.join(root, name), resume))
            if found:
                series_map[entry] = found

        elif entry.lower().endswith(config.VIDEO_EXTS):
            # A file dropped straight into ANIME_DIR — group it by parsed title
            # so manual copies still show up instead of silently vanishing.
            loose.append(_build_episode(abs_entry, resume))

    for ep in loose:
        parsed = release_parser.parse(ep['filename'])
        key = parsed['title'] or os.path.splitext(ep['filename'])[0]
        series_map.setdefault(key, []).append(ep)

    out = []
    for folder_name, episodes in series_map.items():
        series = _series_from_episodes(folder_name, episodes, resume)
        series['added'] = _folder_mtime(folder_name)
        if not include_episodes:
            series.pop('episodes', None)
            series.pop('seasons', None)
        out.append(series)

    out.sort(key=lambda s: s['added'], reverse=True)
    return out


def _folder_mtime(folder_name):
    path = os.path.join(config.ANIME_DIR, folder_name)
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0


def get_series(slug):
    for series in scan():
        if series['slug'] == slug:
            return series
    return None


def resolve(rel_path):
    """Map a library-relative path to an absolute one, refusing escapes."""
    root = os.path.abspath(config.ANIME_DIR)
    full = os.path.abspath(os.path.join(root, rel_path))
    if not (full == root or full.startswith(root + os.sep)):
        return None
    return full


def rename_series(slug, new_name):
    """Rename a series folder, migrating watch progress and cached art.

    Parsed folder names are frequently wrong, so this is the escape hatch.
    Resume keys are stored relative to ANIME_DIR and begin with the folder
    name, so they are rewritten here rather than silently orphaned.
    """
    series = get_series(slug)
    if series is None:
        return {'ok': False, 'error': 'series not found'}

    clean = re.sub(r'\s*:\s*', ' - ', (new_name or '').strip())
    clean = re.sub(r'[\\/:*?"<>|]', '-', clean)
    clean = re.sub(r'\s+', ' ', clean).strip(' .-')
    if not clean:
        return {'ok': False, 'error': 'name cannot be empty'}

    old_folder = series['folder']
    if clean == old_folder:
        return {'ok': True, 'slug': slug, 'folder': old_folder, 'unchanged': True}

    old_path = os.path.join(config.ANIME_DIR, old_folder)
    new_path = os.path.join(config.ANIME_DIR, clean)
    if not os.path.isdir(old_path):
        return {'ok': False, 'error': 'only folder-backed series can be renamed'}
    if os.path.exists(new_path):
        return {'ok': False, 'error': f'"{clean}" already exists'}

    os.rename(old_path, new_path)

    # Carry watch progress across: keys are '<folder>/<rest>'.
    resume = load_resume()
    prefix = old_folder + os.sep
    migrated = {}
    for key, value in resume.items():
        migrated[clean + os.sep + key[len(prefix):] if key.startswith(prefix) else key] = value
    save_resume(migrated)

    # Carry the cached poster and metadata across to the new slug.
    new_slug = slugify(clean)
    for src, dst in ((poster_path(slug), poster_path(new_slug)),
                     (meta_path(slug), meta_path(new_slug))):
        if os.path.isfile(src) and src != dst:
            os.replace(src, dst)

    return {'ok': True, 'slug': new_slug, 'folder': clean}


# ─── Deleting ──────────────────────────────────────────────────────────────

def _has_videos(folder_abs):
    for _root, _dirs, files in os.walk(folder_abs):
        if any(name.lower().endswith(config.VIDEO_EXTS) for name in files):
            return True
    return False


def _series_slug_of(rel_path):
    for series in scan():
        if any(ep['path'] == rel_path for ep in series['episodes']):
            return series['slug']
    return None


def _forget(rel_paths, slug=None):
    """Drop watch progress for these files, and the series' cached art."""
    data = load_resume()
    dropped = [data.pop(rel, None) for rel in rel_paths]
    if any(entry is not None for entry in dropped):
        save_resume(data)
    if slug:
        for path in (poster_path(slug), meta_path(slug)):
            try:
                os.remove(path)
            except OSError:
                pass


def _remove_with_subs(full):
    """Delete a video file and the sidecar subtitles named after it."""
    removed = []
    subs = _find_sidecar_subs(full)
    if os.path.isfile(full):
        os.remove(full)
        removed.append(os.path.relpath(full, config.ANIME_DIR))
    for sub in subs:
        try:
            os.remove(os.path.join(config.ANIME_DIR, sub['path']))
            removed.append(sub['path'])
        except OSError:
            pass
    return removed


def delete_episode(rel_path, keep_folders=()):
    """Delete one episode file and its sidecar subtitles.

    When that was the last video in its series folder, the folder goes too:
    whatever is left there (fonts, .nfo, libtorrent .parts) belonged to the
    release just removed. Folders in `keep_folders` (a download is still
    writing into them) are never removed.
    """
    full = resolve(rel_path)
    if not full or not os.path.isfile(full) or not full.lower().endswith(config.VIDEO_EXTS):
        return {'ok': False, 'error': 'episode not found'}

    rel = os.path.relpath(full, config.ANIME_DIR)
    slug = _series_slug_of(rel)
    size = os.path.getsize(full)
    removed = _remove_with_subs(full)

    top = rel.split(os.sep)[0]
    folder_abs = os.path.join(os.path.abspath(config.ANIME_DIR), top)
    if (os.sep in rel and os.path.isdir(folder_abs)
            and folder_abs not in keep_folders and not _has_videos(folder_abs)):
        shutil.rmtree(folder_abs, ignore_errors=True)

    series_gone = slug is not None and get_series(slug) is None
    _forget([rel], slug if series_gone else None)
    return {'ok': True, 'removed': removed, 'bytes': size, 'series_gone': series_gone}


def delete_series(slug):
    """Delete a series: its folder, any loose files grouped into it, its
    watch progress and its cached artwork."""
    series = get_series(slug)
    if series is None:
        return {'ok': False, 'error': 'series not found'}

    root = os.path.abspath(config.ANIME_DIR)
    folder_abs = resolve(series['folder'])
    if folder_abs and folder_abs != root and os.path.isdir(folder_abs):
        shutil.rmtree(folder_abs)
    # Loose files dropped straight into ANIME_DIR are grouped by title and
    # may share this series; they live outside the folder, so remove them
    # one by one.
    for ep in series['episodes']:
        full = resolve(ep['path'])
        if full and os.path.isfile(full):
            _remove_with_subs(full)

    _forget([ep['path'] for ep in series['episodes']], slug)
    return {'ok': True, 'removed': series['episode_count'], 'bytes': series['total_bytes']}


def backfill_metadata(slug, title, force=False):
    """Fetch AniList metadata and cover for one series, caching both.

    Called after a download finishes and lazily from the UI, so the gallery
    keeps working with no uplink once a series has been seen once.
    """
    if not force and _load_cached_meta(slug) and os.path.isfile(poster_path(slug)):
        return _load_cached_meta(slug)

    meta = anilist.lookup_fuzzy(title)
    if not meta:
        return None
    save_meta(slug, meta)
    if meta.get('cover') and not os.path.isfile(poster_path(slug)):
        anilist.fetch_cover(meta['cover'], poster_path(slug))
    return meta
