"""Drive mpv over its JSON IPC socket.

This is the same mechanism the movie app uses, with two differences that matter
for anime:

1. Proper request framing. mpv interleaves event lines with command replies, so
   a single recv() can hand back an event instead of the answer. We tag each
   command with a request_id and read lines until the matching reply shows up.
   The movie app's single 4 KB recv() is fine for `time-pos` but truncates
   `track-list`, which is exactly what we need.

2. Track enumeration. Anime releases carry subtitles and audio *inside* the
   mkv — soft ASS subs, often a Japanese/English dual-audio pair — rather than
   as sidecar .srt files. So the subtitle menu has to be read off the file at
   runtime instead of being a hardcoded list.
"""

import json
import os
import socket
import subprocess
import threading
import time

import config

_counter = [0]
_lock = threading.Lock()
_process = [None]


def _next_id():
    with _lock:
        _counter[0] += 1
        return _counter[0]


def command(args, timeout=1.5):
    """Send one mpv command. Returns the reply dict, or None if unreachable."""
    request_id = _next_id()
    payload = json.dumps({'command': args, 'request_id': request_id}) + '\n'

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(config.MPV_IPC_PATH)
            sock.sendall(payload.encode('utf-8'))

            buffer = b''
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buffer += chunk

                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    try:
                        message = json.loads(line.decode('utf-8', 'replace'))
                    except ValueError:
                        continue
                    # Skip asynchronous event lines; we want our own reply.
                    if message.get('request_id') == request_id:
                        return message
            return None
    except (OSError, socket.error):
        return None


def get_property(name, default=None):
    reply = command(['get_property', name])
    if isinstance(reply, dict) and reply.get('error') == 'success':
        return reply.get('data', default)
    return default


def set_property(name, value):
    return command(['set_property', name, value])


def is_running():
    return command(['get_property', 'idle-active'], timeout=0.6) is not None


def ensure_running(wait_seconds=6):
    """Start the player if its IPC socket isn't answering.

    On the Pi this launches wserVideoPlayer, the same DRM/KMS mpv binary the
    movie app drives — only one process can own the TV framebuffer, so both
    apps deliberately share one player and one socket.
    """
    if is_running():
        return True

    proc = _process[0]
    if proc is None or proc.poll() is not None:
        try:
            _process[0] = subprocess.Popen(
                [config.MPV_EXE] + config.MPV_ARGS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, FileNotFoundError):
            return False

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(0.25)
        if is_running():
            return True
    return False


def load(abs_path, start_seconds=0):
    if not ensure_running():
        return False
    # `start` is applied to the next loadfile, so set it first.
    set_property('start', str(int(start_seconds or 0)))
    reply = command(['loadfile', abs_path, 'replace'], timeout=3)
    return reply is not None


def stop():
    return command(['stop'])


def quit_player():
    command(['quit'])
    proc = _process[0]
    if proc is not None:
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        _process[0] = None
    return True


def seek(value, mode='relative'):
    return command(['seek', str(value), mode])


def cycle_pause():
    return command(['cycle', 'pause'])


def status():
    """Current playback position, as the remote's 1 s poll needs it."""
    pos = get_property('time-pos')
    if pos is None:
        return None
    duration = get_property('duration') or 0
    percent = get_property('percent-pos') or 0
    total = int(pos)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return {
        'position':  pos,
        'duration':  duration,
        'percent':   percent,
        'paused':    bool(get_property('pause')),
        'time':      f'{hours}:{minutes:02d}:{seconds:02d}',
        'path':      get_property('path') or '',
    }


def tracks():
    """Embedded audio and subtitle tracks of the file currently loaded.

    Returns {'audio': [...], 'sub': [...]} with the ids mpv expects for
    `aid` / `sid`, plus a 'selected' marker so the menu can show current state.
    """
    raw = get_property('track-list') or []
    out = {'audio': [], 'sub': []}
    for track in raw:
        kind = track.get('type')
        if kind not in ('audio', 'sub'):
            continue
        lang = track.get('lang') or ''
        title = track.get('title') or ''
        bits = [b for b in (lang.upper() if lang else '', title) if b]
        label = ' — '.join(bits) or f"Track {track.get('id')}"
        out[kind].append({
            'id':       track.get('id'),
            'label':    label,
            'lang':     lang,
            'title':    title,
            'codec':    track.get('codec') or '',
            'default':  bool(track.get('default')),
            'forced':   bool(track.get('forced')),
            'selected': bool(track.get('selected')),
        })
    return out


def set_track(kind, track_id):
    """Select an audio or subtitle track. `track_id` may be 'no' to disable."""
    prop = {'audio': 'aid', 'sub': 'sid'}.get(kind)
    if not prop:
        return None
    return set_property(prop, track_id)


def add_subtitle_file(abs_path):
    """Load a sidecar subtitle file into the running player."""
    if not os.path.isfile(abs_path):
        return None
    return command(['sub-add', abs_path, 'select'])
