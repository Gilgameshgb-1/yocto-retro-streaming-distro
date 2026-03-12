SUMMARY = "Huberry Stream – MPV video player with Flask web remote"
DESCRIPTION = "A Flask webserver that controls an MPV IPC process, allowing \
phone-based remote control of video playback."
HOMEPAGE = "https://github.com/Gilgameshgb-1/webserver-videoplayer"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRCREV = "${AUTOREV}"
PV = "1.0+git${SRCPV}"

SRC_URI = "git://github.com/Gilgameshgb-1/webserver-videoplayer;protocol=https;branch=main \
           file://huberry-stream.service \
           file://CMakeLists.txt \
           file://main.cpp \
           file://mpv.conf \
          "

S = "${WORKDIR}/git"

DEPENDS = "mpv fmt"

RDEPENDS:${PN} = " \
    python3-core \
    python3-flask \
    python3-modules \
    python3-requests \
    python3-libtorrent-rasterbar \
    mpv \
"

inherit cmake systemd

#   1. Overwrite the Windows CMakeLists.txt with our Linux/Yocto version.
do_configure:prepend() {
    cp ${WORKDIR}/CMakeLists.txt ${S}/CMakeLists.txt
    cp ${WORKDIR}/main.cpp ${S}/main.cpp
    sed -i \
        -e "s|MOVIES_DIR = '/home/pi/movies'|MOVIES_DIR = '/home/root/movies'|" \
        -e "s|os.path.normpath(os.path.join(BASE_PATH, '..', 'build', _MPV_EXE))|'/usr/bin/wserVideoPlayer'|" \
        ${S}/python-remote/remote.py
}

SYSTEMD_SERVICE:${PN} = "huberry-stream.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

APP_DIR = "/opt/huberry-stream"

do_install:append() {
    install -d ${D}${APP_DIR}
    install -d ${D}${APP_DIR}/templates
    install -d ${D}${APP_DIR}/static
    install -d ${D}${APP_DIR}/assets
    install -d ${D}/home/root/movies
    install -d ${D}${systemd_system_unitdir}

    install -m 0755 ${S}/python-remote/remote.py            ${D}${APP_DIR}/remote.py
    install -m 0755 ${S}/python-remote/torrent_downloader.py ${D}${APP_DIR}/torrent_downloader.py

    for f in ${S}/python-remote/templates/*.html; do
        install -m 0644 "$f" ${D}${APP_DIR}/templates/
    done

    if [ -d ${S}/python-remote/static ]; then
        cp -r ${S}/python-remote/static/. ${D}${APP_DIR}/static/
        chown -R root:root ${D}${APP_DIR}/static
    fi

    if [ -d ${S}/python-remote/assets ]; then
        cp -r ${S}/python-remote/assets/. ${D}${APP_DIR}/assets/
        chown -R root:root ${D}${APP_DIR}/assets
    fi

    install -m 0644 ${WORKDIR}/huberry-stream.service ${D}${systemd_system_unitdir}/

    # mpv system-wide config: point libass directly at the font file so
    # it works without needing fc-cache to have been run first.
    install -d ${D}${sysconfdir}/mpv
    install -m 0644 ${WORKDIR}/mpv.conf ${D}${sysconfdir}/mpv/mpv.conf
}

FILES:${PN} += " \
    ${bindir}/wserVideoPlayer \
    ${APP_DIR} \
    /home/root/movies \
    ${systemd_system_unitdir}/huberry-stream.service \
    ${sysconfdir}/mpv/mpv.conf \
"
