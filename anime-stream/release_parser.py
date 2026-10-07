"""Parse anime release names into structured fields.

Nyaa has no metadata API — a search result is just a fansub filename:

    [SubsPlease] Sousou no Frieren - 03 (1080p) [A1B2C3D4].mkv
    [Erai-raws] Sousou no Frieren 2nd Season [1080p CR WEBRip HEVC AAC][MultiSub] (unofficial batch)
    [Salieri] Frieren - Beyond Journey's End S2 - BD (1080p) (HDR) [Dual Audio]

So we strip the decorations we recognise and keep what is left as the
series title. That title is then what we hand to AniList for cover art
and synopsis, and what we use as the library folder name.

Run this file directly to execute the self-tests against real nyaa titles.
"""

import re

VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.ogm', '.webm', '.m4v', '.mov')

# ─── Attribute vocabularies ────────────────────────────────────────────────
# Each entry is (pattern, canonical). Patterns are matched case-insensitively
# against the whole release name; the first hit in list order wins, so the
# more specific spellings must come first.

_RESOLUTION = [
    (r'\b2160p?\b|\b4k\b|\buhd\b',  '2160p'),
    (r'\b1440p\b',                  '1440p'),
    (r'\b1080p?\b|\bfhd\b',         '1080p'),
    (r'\b720p?\b',                  '720p'),
    (r'\b576p\b',                   '576p'),
    (r'\b480p\b',                   '480p'),
]

_CODEC = [
    (r'\bav1\b',                        'AV1'),
    (r'\bhevc\b|\bh\.?\s?265\b|\bx\.?265\b', 'HEVC'),
    (r'\bavc\b|\bh\.?\s?264\b|\bx\.?264\b',  'H264'),
    (r'\bvp9\b',                        'VP9'),
]

_AUDIO = [
    (r'\btruehd\b',             'TrueHD'),
    (r'\bflac\b',               'FLAC'),
    (r'\be-?ac-?3\b|\bddp(?:\s?\d\.\d)?\b', 'EAC3'),   # DDP / DDP2.0 / DDP 5.1
    (r'\bac-?3\b',              'AC3'),
    (r'\bopus\b',               'Opus'),
    (r'\baac\b',                'AAC'),
    (r'\bvorbis\b',             'Vorbis'),
    (r'\bmp3\b',                'MP3'),
]

_SOURCE = [
    (r'\bremux\b',                          'Remux'),
    (r'\bbd-?rip\b|\bblu-?ray\b|\bbd\b',    'BD'),
    (r'\bweb-?dl\b',                        'WEB-DL'),
    (r'\bweb-?rip\b|\bweb\b',               'WEB'),
    (r'\bhdtv\b',                           'HDTV'),
    (r'\bdvd-?rip\b|\bdvd\b',               'DVD'),
    (r'\btv\b',                             'TV'),
]

# Flags are booleans rather than single-valued fields.
_FLAGS = {
    'dual_audio': r'\bdual[\s\-_]?audio\b',
    'multi_audio': r'\bmulti[\s\-_]?audio\b',
    'multi_sub':  r'\bmulti[\s\-_]?subs?\b|\bmultisub\b',
    'hdr':        r'\bhdr(?:10)?(?:\+)?\b|\bdolby[\s\-_]?vision\b|\bdv\b',
    'hardsub':    r'\bhard[\s\-_]?subs?\b',
    'uncensored': r'\buncensored\b',
    'repack':     r'\brepack\d*\b',                 # REPACK, REPACK2
}

# Tokens that mean "this torrent holds many episodes".
_BATCH_WORDS = r'\bbatch\b|\bcomplete\b|\bseason\s+pack\b|\bseasons?\b(?=\s*\d*\s*[-~])'

# Release-note noise that is never part of a series title. Stripped last,
# after season/episode have been pulled out.
_NOISE = [
    r'\bcomplete\s+series\b',
    r'\b(?:unofficial|official)\b', r'\bbatch\b', r'\bcomplete\b',
    r'\b10[\s\-]?bits?\b', r'\b8[\s\-]?bits?\b', r'\bhi10p?\b',
    r'\b(?:2|5|7)\.(?:0|1)\b', r'\bcr\b', r'\bfuni(?:mation)?\b',
    r'\bamzn\b', r'\bnf\b', r'\bbaha\b', r'\bdsnp\b', r'\baniplus\b',
    r'\bsubs?\b', r'\bdubs?\b', r'\beng(?:lish)?\b', r'\bjpn?\b',
    r'\bvostfr\b', r'\braw\b', r'\bencode\b', r'\bsdr\b',
    r'\bmulti\b', r'\bdual\b', r'\baac\s?\d\.\d\b', r'\bdd\+?\s?\d\.\d\b',
    r'\s[-–]\s?[A-Z][A-Za-z0-9]{2,}\s*$',      # trailing scene group, e.g. "-VARYG"
]


def _range_from_chunks(name):
    """Find an episode range living inside a bracketed chunk, e.g. "(001-1000)".

    Bracket contents are discarded before episode parsing, so a batch range
    written inside parens has to be read out before that happens. fullmatch
    keeps "(1080p)" and "(BD Remux 1080p AVC)" from registering as ranges.
    """
    for chunk in re.findall(r'[\[\(]([^\[\]\(\)]*)[\]\)]', name):
        m = re.fullmatch(r'\s*(\d{1,4})\s*[-~]\s*(\d{1,4})\s*', chunk)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if end > start:
                return start, end
    return None, None


def _episode_from_chunks(name):
    """Find an S01E03 tag living inside a bracketed chunk, e.g. "(S01E01)".

    Same reason as _range_from_chunks: brackets are dropped before episode
    parsing, and some groups put the canonical SxxEyy only in there.
    """
    for chunk in re.findall(r'[\[\(]([^\[\]\(\)]*)[\]\)]', name):
        m = re.fullmatch(r'\s*S(\d{1,2})\s*E\s*(\d{1,4})(?:v\d)?\s*', chunk, re.I)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def _find(name, table):
    """Return the canonical value for the first pattern in `table` that hits."""
    for pattern, canonical in table:
        if re.search(pattern, name, re.I):
            return canonical
    return None


def _strip(text, pattern):
    return re.sub(pattern, ' ', text, flags=re.I)


def _tidy(title):
    """Collapse whitespace and shave leftover separators off both ends."""
    title = re.sub(r'[\s_]+', ' ', title)
    title = re.sub(r'\s*[-–~:]\s*$', '', title)
    title = re.sub(r'^\s*[-–~:]\s*', '', title)
    title = re.sub(r'\(\s*\)|\[\s*\]', '', title)
    return title.strip(' .-–_~')


# ─── Season / episode ──────────────────────────────────────────────────────

_ORDINAL = {
    '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
    '6th': 6, '7th': 8, '8th': 8, '9th': 9, '10th': 10,
}
# NOTE: keep this map literal-only; ordinals above 10th are vanishingly rare
# in release names and fall through to season=None.


def _extract_season(text):
    """Pull a season number out of `text`.

    Returns (season, spans_multiple_seasons, text_without_it). Handles `S2`,
    `S02`, `S01-S03`, `2nd Season`, `Season 2` and `Part 2`.
    """
    # S01-S03 / S1-S3 -> a multi-season pack; keep the first, flag the span
    m = re.search(r'\bS(\d{1,2})\s*[-~]\s*S?(\d{1,2})\b', text, re.I)
    if m:
        return int(m.group(1)), True, text[:m.start()] + ' ' + text[m.end():]

    # S01E03 is handled by _extract_episode; match a lone S02 here.
    m = re.search(r'\bS(\d{1,2})(?!\s*E\s*\d)(?:v\d)?\b', text, re.I)
    if m:
        return int(m.group(1)), False, text[:m.start()] + ' ' + text[m.end():]

    # "2nd Season" / "3rd Season"
    m = re.search(r'\b(1st|2nd|3rd|\d+th)\s+Season\b', text, re.I)
    if m:
        return _ORDINAL.get(m.group(1).lower()), False, text[:m.start()] + ' ' + text[m.end():]

    # "Season 2"
    m = re.search(r'\bSeason\s*(\d{1,2})\b', text, re.I)
    if m:
        return int(m.group(1)), False, text[:m.start()] + ' ' + text[m.end():]

    # "Part 2" — not strictly a season but behaves like one for grouping
    m = re.search(r'\bPart\s*(\d{1,2})\b', text, re.I)
    if m:
        return int(m.group(1)), False, text[:m.start()] + ' ' + text[m.end():]

    return None, False, text


def _extract_episode(text):
    """Pull an episode number or range out of `text`.

    Returns (season_hint, episode, ep_start, ep_end, version, text_without_it).
    A range means the torrent is a batch; `episode` is then None. Only the
    `S01E03` form carries a season, so `season_hint` is None otherwise.
    """
    # S01E03 — carries both numbers
    m = re.search(r'\bS(\d{1,2})\s*E\s*(\d{1,4})(?:v(\d))?\b', text, re.I)
    if m:
        return int(m.group(1)), int(m.group(2)), None, None, _int_or_none(m.group(3)), \
               text[:m.start()] + ' ' + text[m.end():]

    # Range: "- 01-12", "(001-1000)", "01~12". Require a dash/paren lead-in so
    # we never mistake a year or a title number for a range.
    m = re.search(r'(?:^|[\s\-–(\[])(\d{1,4})\s*[-~]\s*(\d{1,4})(?=[\s)\]]|$)', text)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if end > start:
            return None, None, start, end, None, text[:m.start()] + ' ' + text[m.end():]

    # Trailing "- 03" / "- 03v2" / "- 1053"
    m = re.search(r'\s[-–]\s*(\d{1,4})(?:v(\d))?\s*$', text)
    if m:
        return None, int(m.group(1)), None, None, _int_or_none(m.group(2)), text[:m.start()]

    # Explicit "E03" / "Ep 03" / "Episode 3"
    m = re.search(r'\bE(?:p|pisode)?\s*[.\-]?\s*(\d{1,4})(?:v(\d))?\b', text, re.I)
    if m:
        return None, int(m.group(1)), None, None, _int_or_none(m.group(2)), \
               text[:m.start()] + ' ' + text[m.end():]

    # Bare trailing number with no dash, e.g. "Bleach 366". Only when the
    # remaining title still has at least one word in front of it.
    m = re.search(r'(?<=\S)\s+(\d{1,4})(?:v(\d))?\s*$', text)
    if m and not re.match(r'^\s*\d', text):
        n = int(m.group(1))
        if not (1900 <= n <= 2100):          # don't eat a year
            return None, n, None, None, _int_or_none(m.group(2)), text[:m.start()]

    return None, None, None, None, None, text


def _int_or_none(v):
    return int(v) if v else None


# ─── Public entry point ────────────────────────────────────────────────────

def parse(raw):
    """Parse a nyaa title or a filename into a dict of release fields."""
    name = (raw or '').strip()

    for ext in VIDEO_EXTS:
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break

    # Scene naming uses dots for spaces: "Frieren.Beyond.Journeys.End.S01E01".
    # Dots between two digits stay, so "DDP2.0" and "5.1" survive intact.
    if ' ' not in name and name.count('.') >= 2:
        name = re.sub(r'(?<!\d)\.|\.(?!\d)', ' ', name)

    # Leading [Group] or (Group)
    group = None
    m = re.match(r'^\s*[\[\(]([^\]\)]+)[\]\)]\s*', name)
    if m:
        group = m.group(1).strip()
        name = name[m.end():]

    # Attributes may sit inside brackets or bare, so scan the whole string.
    resolution = _find(name, _RESOLUTION)
    codec      = _find(name, _CODEC)
    audio      = _find(name, _AUDIO)
    source     = _find(name, _SOURCE)
    flags      = {k: bool(re.search(p, name, re.I)) for k, p in _FLAGS.items()}
    is_batch   = bool(re.search(_BATCH_WORDS, name, re.I))

    # CRC32 stamp, e.g. [A1B2C3D4]
    crc = None
    m = re.search(r'[\[\(]([0-9A-F]{8})[\]\)]', name, re.I)
    if m:
        crc = m.group(1).upper()

    # Everything still in brackets is decoration — drop it, then drop the
    # bare attribute tokens we just recognised.
    chunk_start, chunk_end = _range_from_chunks(name)
    chunk_season, chunk_episode = _episode_from_chunks(name)

    bare = re.sub(r'[\[\(][^\[\]\(\)]*[\]\)]', ' ', name)
    for table in (_RESOLUTION, _CODEC, _AUDIO, _SOURCE):
        for pattern, _ in table:
            bare = _strip(bare, pattern)
    for pattern in _FLAGS.values():
        bare = _strip(bare, pattern)

    season, multi_season, bare = _extract_season(bare)
    # Dropping a bracket mid-name leaves a dangling separator behind, as in
    # "Fate strange fake - 01 (S01E01) - (WEB 1080p)" -> "... - 01  - ".
    # Trim it, or the trailing "- 01" episode rule never sees the number.
    bare = re.sub(r'(?:\s*[-–~]\s*)+$', '', bare.rstrip())
    season_hint, episode, ep_start, ep_end, version, bare = _extract_episode(bare)
    if season is None:
        season = season_hint if season_hint is not None else chunk_season
    if ep_start is None:
        ep_start, ep_end = chunk_start, chunk_end
    if episode is None and ep_start is None:
        episode = chunk_episode

    for pattern in _NOISE:
        bare = _strip(bare, pattern)

    title = _tidy(bare)

    # A range, a multi-season span, or a season named with no episode all mean
    # the torrent holds more than one episode.
    if ep_start is not None or multi_season or (season is not None and episode is None):
        is_batch = True

    return {
        'raw':         raw,
        'title':       title,
        'group':       group,
        'season':      season,
        'episode':     episode,
        'ep_start':    ep_start,
        'ep_end':      ep_end,
        'version':     version,
        'resolution':  resolution,
        'codec':       codec,
        'audio':       audio,
        'source':      source,
        'crc':         crc,
        'is_batch':    is_batch,
        **flags,
    }


# ─── Raspberry Pi 5 playback capability ────────────────────────────────────
# The Pi 5 has a hardware HEVC decoder good for 4Kp60, but no hardware H.264
# decoder (that block was dropped after the Pi 4) and no AV1 decoder at all.
# Software decode is comfortable at 1080p and hopeless at 2160p.

def playback_warning(resolution, codec):
    """Return a human-readable warning if the Pi 5 will struggle, else None."""
    if codec == 'AV1':
        if resolution == '2160p':
            return 'AV1 has no hardware decode on the Pi 5 — 4K AV1 will not play'
        return 'AV1 is software-decoded on the Pi 5 and may stutter'
    if resolution == '2160p' and codec == 'H264':
        return '4K H.264 is software-decoded on the Pi 5 and will likely stutter'
    if resolution == '2160p' and codec is None:
        return '4K with an unknown codec — only HEVC is hardware-decoded on the Pi 5'
    return None


if __name__ == '__main__':
    # Real titles pulled from the nyaa RSS feed, plus a few known-awkward ones.
    CASES = [
        "[Erai-raws] Sousou no Frieren 2nd Season [1080p CR WEBRip HEVC AAC][MultiSub] (unofficial batch)",
        "[AUTISM] Sousou no Frieren - S01v2 (BD Remux 1080p AVC FLAC/TrueHD/AAC 2.0/5.1) [Dual-Audio, Multi-Audio, Multi-Sub]",
        "[Salieri] Frieren - Beyond Journey's End S2 - BD (1080p) (HDR) [Dual Audio]",
        "[SubsPlease] Sousou no Frieren - 03 (1080p) [A1B2C3D4].mkv",
        "[SubsPlease] Dandadan - 12 (2160p) [9F2E1C04].mkv",
        "[Judas] Kaguya-sama wa Kokurasetai S01-S03 (BD 1080p x265 10bit)",
        "[Anime Time] One Piece (001-1000) [Batch] [1080p][HEVC][x265]",
        "[Beatrice-Raws] Violet Evergarden 01 [BDRip 2160p HEVC TrueHD]",
        "[ToonsHub] Solo Leveling S02E05 (1080p AV1 AAC) [Dual Audio]",
        "Mushishi Complete Series (BD 720p)",
        # SxxEyy only inside brackets, and a separator left dangling after them
        "[Kaleido-subs] Fate strange fake - 01 (S01E01) - (WEB 1080p HEVC x265 10-bit E-AC-3 2.0) [Dual Audio] [82ED1AAF].mkv",
        # Scene naming: dots for spaces, numbered REPACK, DDP2.0 audio
        "Frieren.Beyond.Journeys.End.S01E01.REPACK2.1080p.WEBRip.Dual-Audio.DDP2.0.x265-Arg0.mkv",
    ]
    width = max(len(c['title']) for c in map(parse, CASES)) + 2
    print(f"{'TITLE'.ljust(width)} SEA  EP     RES    CODEC  BATCH  GROUP")
    print('-' * (width + 46))
    for raw in CASES:
        p = parse(raw)
        ep = (f"{p['ep_start']}-{p['ep_end']}" if p['ep_start'] is not None
              else (str(p['episode']) if p['episode'] is not None else '-'))
        print(f"{p['title'].ljust(width)} "
              f"{str(p['season'] or '-').ljust(4)} "
              f"{ep.ljust(6)} "
              f"{str(p['resolution'] or '-').ljust(6)} "
              f"{str(p['codec'] or '-').ljust(6)} "
              f"{str(p['is_batch']).ljust(6)} "
              f"{p['group'] or '-'}")
        w = playback_warning(p['resolution'], p['codec'])
        if w:
            print(f"{' ' * width}  ! {w}")
