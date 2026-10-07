"""Convert sidecar subtitle files to WebVTT for the in-browser player.

The movie app handles .srt only. Anime fansubs overwhelmingly ship .ass
(SubStation Alpha) when they ship anything sidecar at all, so both are handled
here. ASS styling, positioning and karaoke effects cannot survive the trip to
WebVTT — we keep the dialogue and the timings and drop the rest, which is the
honest subset a browser can render.
"""

import re

_SRT_TIME = re.compile(r'(\d{1,2}:\d{2}:\d{2}),(\d{3})')
_ASS_OVERRIDE = re.compile(r'\{[^}]*\}')


def srt_to_vtt(content):
    # 00:00:01,000 -> 00:00:01.000
    return 'WEBVTT\n\n' + _SRT_TIME.sub(r'\1.\2', content)


def _ass_timestamp(value):
    """ASS uses H:MM:SS.cc (centiseconds); WebVTT wants HH:MM:SS.mmm."""
    match = re.match(r'\s*(\d+):(\d{2}):(\d{2})[.,](\d{1,3})\s*$', value)
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    millis = int(fraction.ljust(3, '0')[:3]) if len(fraction) >= 3 \
        else int(fraction) * (10 ** (3 - len(fraction)))
    return f'{int(hours):02d}:{minutes}:{seconds}.{millis:03d}'


def ass_to_vtt(content):
    lines = content.splitlines()
    text_index = 9
    start_index, end_index = 1, 2
    in_events = False
    cues = []

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith('['):
            in_events = stripped.lower().startswith('[events]')
            continue
        if not in_events:
            continue

        if stripped.lower().startswith('format:'):
            fields = [f.strip().lower() for f in stripped.split(':', 1)[1].split(',')]
            if 'start' in fields:
                start_index = fields.index('start')
            if 'end' in fields:
                end_index = fields.index('end')
            if 'text' in fields:
                text_index = fields.index('text')
            continue

        if not stripped.lower().startswith('dialogue:'):
            continue

        # Text is the last field and may itself contain commas, so split only
        # as many times as there are fields before it.
        parts = stripped.split(':', 1)[1].split(',', text_index)
        if len(parts) <= text_index:
            continue

        start = _ass_timestamp(parts[start_index])
        end = _ass_timestamp(parts[end_index])
        if not start or not end:
            continue

        text = parts[text_index]
        text = _ASS_OVERRIDE.sub('', text)          # drop {\pos}, {\i1}, karaoke
        text = text.replace('\\N', '\n').replace('\\n', '\n')
        text = re.sub(r'\\h', ' ', text).strip()
        if not text:
            continue

        cues.append((start, end, text))

    body = '\n\n'.join(f'{s} --> {e}\n{t}' for s, e, t in cues)
    return 'WEBVTT\n\n' + body


def to_vtt(content, filename):
    lower = filename.lower()
    if lower.endswith(('.ass', '.ssa')):
        return ass_to_vtt(content)
    if lower.endswith('.vtt'):
        return content if content.lstrip().startswith('WEBVTT') else 'WEBVTT\n\n' + content
    return srt_to_vtt(content)
