# anime-stream

An episodic anime library for the retro box: search nyaa.si, download, and watch
either on the TV or in the phone browser. Third web app alongside the game
launcher (`retro.pi`) and the movie player (`stream.pi`), on its own port with
its own nginx vhost and systemd unit.

The movie app is built around *one folder, one film*. Anime is not — a single
torrent is often a whole cour — so this is structured as **series → seasons →
episodes**, with per-episode watch state and a resume button that picks up the
first unfinished episode.

## Running it locally

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py   # starts on :5003
```

Then open <http://localhost:5003>. Episodes go in `./anime-library/<series>/`.

Playback on a laptop spawns a windowed `mpv`; on the Pi it drives the DRM/KMS
player instead. Nothing else differs.

### Downloads

Downloading needs `libtorrent`. On Ubuntu 24.04 pip handles it:

```bash
.venv/bin/pip install libtorrent
```

If your platform has no wheel, use the distro package and a venv that can see
it (`sudo apt install python3-libtorrent`, then recreate the venv with
`--system-site-packages`). **Without libtorrent everything else still works** —
search, library, playback — and only the download button is disabled.

## How it fits together

| File | Responsibility |
|---|---|
| `app.py` | Flask routes, HTTP range streaming, watch progress |
| `nyaa.py` | nyaa.si search over RSS; magnet building; filtering and sorting |
| `release_parser.py` | Fansub filename → series, season, episode, resolution, codec |
| `anilist.py` | Cover art, synopsis, scores; disk-cached, fuzzy title matching |
| `library.py` | Scans `ANIME_DIR` into the series tree; resume state; rename |
| `player.py` | mpv JSON IPC, including embedded audio/subtitle track selection |
| `downloader.py` | libtorrent session, per-series save folders |
| `subtitles.py` | Sidecar `.srt` **and** `.ass` → WebVTT for the browser player |
| `static/` | Phone UI. Lexend is bundled in `static/fonts/` (OFL-1.1) because the Pi's hotspot has no uplink for web fonts |

### Why nyaa needs a parser

Nyaa has no JSON API, but every search is also an RSS feed carrying an
`infoHash` — so magnets are built locally and `.torrent` files are never
fetched. What it does *not* carry is any structure: a result is a filename like

```
[SubsPlease] Sousou no Frieren - 03 (1080p) [A1B2C3D4].mkv
```

`release_parser.py` pulls that apart. Run it directly to see it work against
real-world titles, scene naming included:

```bash
python3 release_parser.py
```

It will not win every time — scene releases embed episode titles no parser can
separate from the show name. That is why the download dialog shows the target
folder as an **editable field with AniList suggestions**, and why series can be
renamed afterwards (pencil icon in the series header). Renaming migrates watch
progress and cached artwork along with the folder.

### Nyaa's RSS ignores its own sort parameters

Worth knowing before you trust `&s=seeders`: asking for `s=seeders` and `s=id`
returns byte-identical feeds. The endpoint always serves a **newest-first window
of the latest 75 matches**. Sorting therefore happens in Python, in
`nyaa.sort_results()`, over that window — so "most seeders" means most-seeded
*of the newest 75*, not of all nyaa. The results line in the UI says so. To go
wider, page through `&p=2,3…` and sort the union.

## Playback

Two destinations, same as the movie app:

**TV** — mpv over JSON IPC. On the Pi this is huberry-stream's
`wserVideoPlayer` on `/tmp/mpv-socket`, deliberately shared with the movie app:
only one process can own the framebuffer, and only one thing plays on the TV at
a time.

Unlike the movie remote, the subtitle and audio menus are read from the file at
runtime via mpv's `track-list`. Anime ships soft ASS subs and dual Japanese/
English audio muxed inside the mkv, so a hardcoded menu is useless. This also
needs proper IPC framing — mpv interleaves event lines with command replies, and
a single 4 KB `recv()` truncates `track-list`.

**Phone** — HTTP range requests to an HTML5 `<video>`. Two honest limits the UI
states rather than failing silently:

- Browsers cannot read subtitles muxed into the mkv. Only sidecar files are
  offered here; embedded tracks are TV-only.
- HEVC and AV1 frequently will not decode in a phone browser.

## 4K on the Pi 5

The Pi 5 has a hardware HEVC decoder good for 4Kp60. It has **no** hardware
H.264 decoder (that block was dropped after the Pi 4) and **no** AV1 decoder.
Software decode is comfortable at 1080p and hopeless at 2160p.

So `release_parser.playback_warning()` flags, in search results:

| Release | Verdict |
|---|---|
| 2160p HEVC | fine — hardware decoded |
| 2160p AV1 | will not play |
| 2160p H.264 | software decoded, will stutter |
| 2160p, codec unknown | only HEVC is safe at 4K |

Search results also flag anything over `ANIME_WARN_SIZE_GB` (default 25) —
nyaa serves BD remuxes north of 200 GB — and anything under 60 MB, which is a
subtitle pack rather than video.

## Configuration

Every path is an environment variable with a laptop-friendly default, so the
same code runs in both places. The systemd unit sets them on the Pi.

| Variable | Default (local) | On the Pi |
|---|---|---|
| `ANIME_DIR` | `./anime-library` | `/movies/anime` |
| `ANIME_STATE_DIR` | `./.state` | `/home/root/.anime-stream` |
| `ANIME_TARGET` | *(auto)* | `pi` — selects the DRM player path |
| `MPV_EXE` | `mpv` | `/usr/bin/wserVideoPlayer` |
| `MPV_IPC_PATH` | `/tmp/mpv-anime-socket` | `/tmp/mpv-socket` |
| `FLASK_PORT` | `5003` | `5003` |
| `ANIME_WARN_SIZE_GB` | `25` | `25` |
| `ANIME_REQUIRE_MOUNT` | *(unset)* | `/movies` — downloads are refused, and running ones stopped, if the SSD is not mounted there |

## Deploying to the Pi

Packaged by `meta-my-retro/recipes-apps/anime-stream/`, installed to
`/opt/anime-stream`, reachable at **`http://anime.pi`** once the image is built:

```bash
kas build kas-project.yml
```

The recipe pulls its source from this directory via `FILESEXTRAPATHS`, so there
is one copy of the code and no sync step. That relies on `meta-my-retro` living
inside this repo, which it does. If the app is ever split into its own git repo
— as `webserver-videoplayer` was — replace that with a `git://` `SRC_URI`.

`ANIME_DIR` defaults to `/movies/anime`, a subdirectory of the existing movies
partition, so **no repartitioning is needed** and nothing on the NVMe is at
risk. To give anime its own partition later, change the one `Environment=` line
in `anime-stream.service` and add the partition to `setup-nvme.sh`. That script
keeps existing `games`/`movies` filesystems and only formats a blank drive, so
reflashing the SD card leaves the library intact.

## API

| Route | Purpose |
|---|---|
| `GET /api/library` | Series list for the gallery |
| `GET /api/series/<slug>` | One series with seasons and episodes |
| `POST /api/series/<slug>/rename` | Rename folder, migrating progress and art |
| `GET /api/search` | nyaa search — `q`, `sort`, `resolution`, `batch`, `trusted`, `min_gb`, `max_gb` |
| `GET /api/resolve-title` | AniList canonical titles for a parsed release name |
| `POST /api/download` | Start a magnet into a series folder |
| `GET /api/downloads` | Progress, rate, peers, ETA |
| `POST /api/downloads/pause` | Pause or resume one download |
| `POST /api/downloads/cancel` | Stop; optionally delete partial files |
| `GET /api/play` | Load an episode on the TV, resuming where you left off |
| `GET /api/status` | Position, duration, paused |
| `GET /api/tracks` · `POST /api/track` | Embedded audio/subtitle tracks |
| `GET /stream/<path>` | Range-request video for the browser |
| `GET /api/subtitles` · `GET /subtitles/<path>` | Sidecar subs, converted to WebVTT |
| `GET`/`POST` `/api/resume` · `POST /api/watched` | Watch progress |
| `GET /api/health` | Paths, libtorrent availability, player state |

## Known limitations

- Sorting covers nyaa's newest-75 window, not all of nyaa (see above).
- No RSS subscriptions — every download is chosen by hand, by design.
- Batch torrents download in full; there is no per-episode file selection.
- Series grouping keys off the folder name, so two spellings of one show make
  two series until one is renamed.
