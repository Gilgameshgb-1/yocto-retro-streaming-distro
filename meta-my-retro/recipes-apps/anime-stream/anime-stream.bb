SUMMARY = "Anime library, nyaa.si search and player"
DESCRIPTION = "Flask web app serving an episodic anime library. Searches \
nyaa.si over its RSS feed, pulls artwork and metadata from AniList, downloads \
via libtorrent, and plays either on the TV through the shared mpv instance or \
in the phone browser over HTTP range requests."
HOMEPAGE = "https://github.com/Gilgameshgb-1"
# The app is MIT. static/fonts/ bundles the Lexend typeface, which is OFL-1.1;
# it ships locally because the hotspot has no uplink to fetch web fonts.
LICENSE = "MIT & OFL-1.1"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302 \
                    file://${COMMON_LICENSE_DIR}/OFL-1.1;md5=fac3a519e5e9eb96316656e0ca4f2b90"

# The app source lives at the repo root rather than under this recipe, so it
# stays runnable on a laptop (python3 app.py) without a Yocto build. meta-my-retro
# is a directory of this repo — see kas-project.yml — so the relative hop out of
# the layer is safe here. If the app is ever split into its own git repo, as
# webserver-videoplayer was, swap this for a git:// SRC_URI.
FILESEXTRAPATHS:prepend := "${THISDIR}/../../../anime-stream:"

SRC_URI = " \
    file://app.py \
    file://config.py \
    file://nyaa.py \
    file://anilist.py \
    file://library.py \
    file://player.py \
    file://downloader.py \
    file://release_parser.py \
    file://subtitles.py \
    file://templates/ \
    file://static/ \
    file://anime-stream.service \
"

S = "${WORKDIR}"

inherit systemd allarch

RDEPENDS:${PN} = " \
    python3-core \
    python3-flask \
    python3-modules \
    python3-requests \
    python3-libtorrent-rasterbar \
    mpv \
    huberry-stream \
"

# huberry-stream provides /usr/bin/wserVideoPlayer. Both apps drive the one mpv
# instance over the same IPC socket on purpose: only one process can own the
# TV framebuffer, and only one thing plays on the TV at a time.

SYSTEMD_SERVICE:${PN} = "anime-stream.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

APP_DIR = "/opt/anime-stream"
ANIME_DIR ?= "/movies/anime"

do_install() {
    install -d ${D}${APP_DIR}
    install -d ${D}${APP_DIR}/templates
    install -d ${D}${APP_DIR}/static
    install -d ${D}${systemd_system_unitdir}

    for module in app config nyaa anilist library player downloader \
                  release_parser subtitles; do
        install -m 0644 ${S}/$module.py ${D}${APP_DIR}/
    done
    chmod 0755 ${D}${APP_DIR}/app.py

    install -m 0644 ${S}/templates/*.html ${D}${APP_DIR}/templates/
    cp -r ${S}/static/. ${D}${APP_DIR}/static/
    chown -R root:root ${D}${APP_DIR}/static

    # Media root. If the NVMe is present this is a directory on the movies
    # partition; if it is not, the app still starts and shows an empty library.
    install -d ${D}${ANIME_DIR}

    install -m 0644 ${WORKDIR}/anime-stream.service ${D}${systemd_system_unitdir}/
}

FILES:${PN} += " \
    ${APP_DIR} \
    ${ANIME_DIR} \
    ${systemd_system_unitdir}/anime-stream.service \
"
