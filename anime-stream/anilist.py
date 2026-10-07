"""Fetch anime metadata and cover art from AniList.

Nyaa gives us a filename and nothing else — no poster, no synopsis, no episode
count. AniList's public GraphQL endpoint fills that in, needs no API key, and
accepts both romaji and English titles, which matters because fansub groups use
either ("Sousou no Frieren" vs "Frieren: Beyond Journey's End").

Results are cached to disk. Covers are saved into each series folder so the
library still renders when the Pi is serving its own hotspot with no uplink.
"""

import json
import os
import re
import threading
import time

import requests

import config

ENDPOINT = 'https://graphql.anilist.co'

# AniList allows 90 requests/minute. We are nowhere near that, but a floor
# between calls keeps us polite during a library-wide backfill.
_MIN_INTERVAL = 0.7
_last_call = [0.0]
_lock = threading.Lock()

_QUERY = '''
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title { romaji english native }
    format
    status
    episodes
    duration
    seasonYear
    season
    averageScore
    genres
    studios(isMain: true) { nodes { name } }
    coverImage { large extraLarge color }
    bannerImage
    description(asHtml: false)
  }
}
'''

_cache = None


def _load_cache():
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(config.META_CACHE, 'r', encoding='utf-8') as f:
            _cache = json.load(f)
    except (OSError, ValueError):
        _cache = {}
    return _cache


def _save_cache():
    config.ensure_dirs()
    tmp = config.META_CACHE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_cache, f, indent=1)
    os.replace(tmp, config.META_CACHE)


def _cache_key(title):
    return re.sub(r'[^a-z0-9]+', '', (title or '').lower())


def _strip_html(text):
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _throttle():
    with _lock:
        wait = _MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def lookup(title, use_cache=True):
    """Return a metadata dict for `title`, or None if nothing matched.

    A miss is cached too — otherwise every library scan re-queries AniList for
    the one release whose name the parser could not clean up.
    """
    key = _cache_key(title)
    if not key:
        return None

    cache = _load_cache()
    if use_cache and key in cache:
        return cache[key]

    _throttle()
    try:
        resp = requests.post(
            ENDPOINT,
            json={'query': _QUERY, 'variables': {'search': title}},
            timeout=15,
            headers={'User-Agent': 'my-retro-os/anime-stream'},
        )
        if resp.status_code == 429:
            retry = int(resp.headers.get('Retry-After', '5'))
            time.sleep(min(retry, 30))
            resp = requests.post(
                ENDPOINT,
                json={'query': _QUERY, 'variables': {'search': title}},
                timeout=15,
                headers={'User-Agent': 'my-retro-os/anime-stream'},
            )
        resp.raise_for_status()
        media = (resp.json().get('data') or {}).get('Media')
    except (requests.RequestException, ValueError):
        # Offline or AniList down — don't poison the cache with a false miss.
        return None

    if not media:
        cache[key] = None
        _save_cache()
        return None

    studios = [n['name'] for n in (media.get('studios') or {}).get('nodes', [])]
    info = {
        'anilist_id':  media.get('id'),
        'title_romaji':  (media.get('title') or {}).get('romaji') or '',
        'title_english': (media.get('title') or {}).get('english') or '',
        'format':      media.get('format'),
        'status':      media.get('status'),
        'episodes':    media.get('episodes'),
        'duration':    media.get('duration'),
        'year':        media.get('seasonYear'),
        'season':      media.get('season'),
        'score':       media.get('averageScore'),
        'genres':      media.get('genres') or [],
        'studios':     studios,
        'cover':       (media.get('coverImage') or {}).get('extraLarge')
                       or (media.get('coverImage') or {}).get('large') or '',
        'color':       (media.get('coverImage') or {}).get('color') or '',
        'banner':      media.get('bannerImage') or '',
        'synopsis':    _strip_html(media.get('description')),
    }

    cache[key] = info
    _save_cache()
    return info


def lookup_fuzzy(title):
    """lookup(), then progressively shorter prefixes of the title.

    Release and folder names routinely carry episode titles, version tags
    and alternate names ("Frieren - Beyond Journey's End - v3 - Sousou no
    Frieren"), which AniList will not match whole. The leading words
    almost always do match, so fall back to those.
    """
    if not title:
        return None

    meta = lookup(title)
    if meta:
        return meta

    # Split on separators too, so 'A - B - C' also tries just 'A'.
    trimmed = re.split(r'\s+-\s+', title)[0].strip()
    if trimmed and trimmed != title:
        meta = lookup(trimmed)
        if meta:
            return meta
        title = trimmed

    words = title.split()
    for length in range(min(len(words) - 1, 6), 1, -1):
        meta = lookup(' '.join(words[:length]))
        if meta:
            return meta
    return None


def fetch_cover(url, dest_path, timeout=20):
    """Download a cover image to `dest_path`. Returns True on success."""
    if not url:
        return False
    try:
        resp = requests.get(url, timeout=timeout,
                            headers={'User-Agent': 'my-retro-os/anime-stream'})
        resp.raise_for_status()
        tmp = dest_path + '.part'
        with open(tmp, 'wb') as f:
            f.write(resp.content)
        os.replace(tmp, dest_path)
        return True
    except (requests.RequestException, OSError):
        return False
