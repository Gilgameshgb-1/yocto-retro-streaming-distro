"""Search nyaa.si via its RSS feed.

Nyaa has no JSON API, but every search is also exposed as RSS, and the feed
carries everything we need in a `nyaa:` namespace — info hash, seeders, size,
trusted flag. That means no HTML scraping and no fetching .torrent files: the
info hash alone is enough to build a magnet link.

Each item is run through release_parser so the UI can show resolution, codec
and episode info instead of a raw fansub filename.
"""

import email.utils
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

import release_parser

BASE_URL = 'https://nyaa.si/'

NS = {'nyaa': 'https://nyaa.si/xmlns/nyaa'}

# The trackers nyaa itself embeds in its magnet links.
TRACKERS = [
    'http://nyaa.tracker.wf:7777/announce',
    'udp://open.stealth.si:80/announce',
    'udp://tracker.opentrackr.org:1337/announce',
    'udp://exodus.desync.com:6969/announce',
    'udp://tracker.torrent.eu.org:451/announce',
]

# Nyaa's own category ids.
CATEGORIES = {
    'english':  '1_2',   # Anime - English-translated
    'raw':      '1_4',   # Anime - Raw
    'non_eng':  '1_3',   # Anime - Non-English-translated
    'amv':      '1_1',   # Anime Music Video
    'all':      '1_0',   # everything under Anime
}

# f= filter values.
FILTERS = {
    'none':     '0',
    'no_remake': '1',
    'trusted':  '2',
}

# Nyaa's RSS endpoint ignores the s= and o= sort parameters: asking for
# s=seeders and s=id returns byte-identical feeds. The feed is always a
# newest-first window of the most recent 75 matches, so sorting has to be
# done here, over that window. SORT_KEYS below is the real implementation.
SORT_KEYS = {
    'seeders':  lambda r: -r['seeders'],
    'newest':   lambda r: -r['published_ts'],
    'largest':  lambda r: -r['size_bytes'],
    'smallest': lambda r: r['size_bytes'],
}
DEFAULT_SORT = 'seeders'

_SIZE_UNITS = {
    'b': 1,
    'kib': 1024, 'kb': 1000,
    'mib': 1024 ** 2, 'mb': 1000 ** 2,
    'gib': 1024 ** 3, 'gb': 1000 ** 3,
    'tib': 1024 ** 4, 'tb': 1000 ** 4,
}


def parse_size(text):
    """"6.6 GiB" -> 7086696038. Returns 0 when unparseable."""
    if not text:
        return 0
    m = re.match(r'\s*([\d.]+)\s*([A-Za-z]+)\s*$', text)
    if not m:
        return 0
    try:
        value = float(m.group(1))
    except ValueError:
        return 0
    return int(value * _SIZE_UNITS.get(m.group(2).lower(), 1))


def human_size(num_bytes):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if num_bytes < 1024 or unit == 'TiB':
            return f'{num_bytes:.1f} {unit}' if unit != 'B' else f'{num_bytes} B'
        num_bytes /= 1024
    return f'{num_bytes:.1f} TiB'


def build_magnet(info_hash, display_name):
    """Assemble a magnet from the info hash — no need to fetch the .torrent."""
    magnet = f'magnet:?xt=urn:btih:{info_hash}'
    if display_name:
        magnet += f'&dn={urllib.parse.quote(display_name)}'
    for tracker in TRACKERS:
        magnet += f'&tr={urllib.parse.quote(tracker)}'
    return magnet


def _text(item, tag):
    el = item.find(tag, NS)
    return el.text.strip() if el is not None and el.text else ''

def _pubdate_ts(value):
    """RFC-822 pubDate to a unix timestamp; 0 when absent or malformed."""
    if not value:
        return 0
    try:
        return int(email.utils.parsedate_to_datetime(value).timestamp())
    except (TypeError, ValueError):
        return 0


def sort_results(results, key=DEFAULT_SORT):
    """Sort a result list. Falls back to seeders for an unknown key."""
    return sorted(results, key=SORT_KEYS.get(key, SORT_KEYS[DEFAULT_SORT]))


def search(query, category='english', filter_mode='none', page=1, timeout=15):
    """Run a nyaa search and return a list of parsed release dicts.

    Raises requests.RequestException if nyaa is unreachable — callers surface
    that to the UI rather than pretending there were no results.
    """
    params = {
        'page': 'rss',
        'q':    query or '',
        'c':    CATEGORIES.get(category, CATEGORIES['english']),
        'f':    FILTERS.get(filter_mode, FILTERS['none']),
    }
    if page and int(page) > 1:
        params['p'] = int(page)

    resp = requests.get(BASE_URL, params=params, timeout=timeout,
                        headers={'User-Agent': 'my-retro-os/anime-stream'})
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    results = []

    for item in root.iterfind('./channel/item'):
        title     = (item.findtext('title') or '').strip()
        info_hash = _text(item, 'nyaa:infoHash')
        if not info_hash:
            continue

        size_text  = _text(item, 'nyaa:size')
        size_bytes = parse_size(size_text)
        parsed     = release_parser.parse(title)

        results.append({
            'id':         (item.findtext('guid') or '').rsplit('/', 1)[-1],
            'raw_title':  title,
            'view_url':   item.findtext('guid') or '',
            'info_hash':  info_hash,
            'magnet':     build_magnet(info_hash, title),
            'size_text':  size_text,
            'size_bytes': size_bytes,
            'seeders':    int(_text(item, 'nyaa:seeders') or 0),
            'leechers':   int(_text(item, 'nyaa:leechers') or 0),
            'downloads':  int(_text(item, 'nyaa:downloads') or 0),
            'category':   _text(item, 'nyaa:category'),
            'trusted':    _text(item, 'nyaa:trusted').lower() == 'yes',
            'remake':     _text(item, 'nyaa:remake').lower() == 'yes',
            'published':  item.findtext('pubDate') or '',
            'published_ts': _pubdate_ts(item.findtext('pubDate')),
            # merged release_parser output
            'title':      parsed['title'],
            'group':      parsed['group'],
            'season':     parsed['season'],
            'episode':    parsed['episode'],
            'ep_start':   parsed['ep_start'],
            'ep_end':     parsed['ep_end'],
            'resolution': parsed['resolution'],
            'codec':      parsed['codec'],
            'audio':      parsed['audio'],
            'source':     parsed['source'],
            'is_batch':   parsed['is_batch'],
            'dual_audio': parsed['dual_audio'],
            'multi_sub':  parsed['multi_sub'],
            'hdr':        parsed['hdr'],
            'warning':    release_parser.playback_warning(
                              parsed['resolution'], parsed['codec']),
        })

    return results


def apply_filters(results, resolution=None, min_seeders=0, max_size_bytes=None,
                  batch=None, trusted_only=False, min_size_bytes=None):
    """Narrow a result list client-side.

    Nyaa's own query syntax can't express "1080p only" reliably — release names
    spell resolution a dozen ways — so filtering happens here on parsed fields.
    `batch`: True for batches only, False for single episodes only, None for both.
    """
    out = []
    for r in results:
        if resolution and r['resolution'] != resolution:
            continue
        if r['seeders'] < min_seeders:
            continue
        if max_size_bytes and r['size_bytes'] > max_size_bytes:
            continue
        if min_size_bytes and r['size_bytes'] < min_size_bytes:
            continue
        if batch is True and not r['is_batch']:
            continue
        if batch is False and r['is_batch']:
            continue
        if trusted_only and not r['trusted']:
            continue
        out.append(r)
    return out
