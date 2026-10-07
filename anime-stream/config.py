"""Runtime configuration.

Everything that differs between "running on my laptop" and "running on the Pi"
is an environment variable with a laptop-friendly default, so the same code
runs in both places. The Yocto recipe sets these in the systemd unit.
"""

import os
import platform

_HERE = os.path.dirname(os.path.abspath(__file__))


def _env(name, default):
    return os.environ.get(name, default)


# ─── Where anime lives ─────────────────────────────────────────────────────
# Anime gets its own root, separate from the movie library. On the Pi this
# becomes /movies/anime (or /anime if a dedicated partition is added later) —
# a single value either way.
ANIME_DIR = os.path.abspath(_env('ANIME_DIR', os.path.join(_HERE, 'anime-library')))

# Sidecar state: watch progress, and the AniList lookups we've already done.
STATE_DIR   = os.path.abspath(_env('ANIME_STATE_DIR', os.path.join(_HERE, '.state')))
RESUME_FILE = os.path.join(STATE_DIR, 'resume.json')
META_CACHE  = os.path.join(STATE_DIR, 'anilist-cache.json')

# ─── Player ────────────────────────────────────────────────────────────────
# On the Pi the TV output is mpv on DRM/KMS, driven through the same IPC socket
# the movie app uses — only one thing can own the framebuffer, and only one
# thing plays on the TV at a time, so sharing it is correct rather than a
# compromise. Locally we spawn a plain windowed mpv on our own socket.
ON_PI = _env('ANIME_TARGET', '') == 'pi' or platform.machine() in ('aarch64', 'armv7l')

if ON_PI:
    MPV_IPC_PATH = _env('MPV_IPC_PATH', '/tmp/mpv-socket')
    MPV_EXE      = _env('MPV_EXE', '/usr/bin/wserVideoPlayer')
    MPV_ARGS     = []
else:
    MPV_IPC_PATH = _env('MPV_IPC_PATH', '/tmp/mpv-anime-socket')
    MPV_EXE      = _env('MPV_EXE', 'mpv')
    MPV_ARGS     = [
        '--idle=yes',
        '--force-window=yes',
        '--keep-open=yes',
        f'--input-ipc-server={MPV_IPC_PATH}',
    ]

# ─── Network ───────────────────────────────────────────────────────────────
HOST = _env('FLASK_HOST', '0.0.0.0')
PORT = int(_env('FLASK_PORT', '5003'))

# ─── Download guards ───────────────────────────────────────────────────────
# Nyaa happily serves 200 GB BD remuxes. Warn well before one fills the NVMe.
WARN_SIZE_BYTES = int(_env('ANIME_WARN_SIZE_GB', '25')) * 1024 ** 3

# A mount point that must really be mounted before anything is downloaded —
# /movies on the Pi. If the SSD is missing, /movies is just an empty folder on
# the SD card, and a big download would silently fill the card. Unset on a
# laptop, which has no SSD to wait for.
REQUIRE_MOUNT = _env('ANIME_REQUIRE_MOUNT', '')

VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.webm', '.m4v', '.mov', '.ogm')
SUB_EXTS   = ('.srt', '.ass', '.ssa', '.vtt', '.sub')


def storage_problem():
    """Why nothing may be downloaded right now, or None if storage is fine."""
    if REQUIRE_MOUNT and not os.path.ismount(REQUIRE_MOUNT):
        return (f'The SSD is not mounted at {REQUIRE_MOUNT}, so this would '
                'download onto the SD card. Check the drive and try again.')
    return None


def ensure_dirs():
    # Don't create the library on the SD card when the SSD is missing; it
    # would only be hidden underneath the SSD once that mounts.
    if not storage_problem():
        os.makedirs(ANIME_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
