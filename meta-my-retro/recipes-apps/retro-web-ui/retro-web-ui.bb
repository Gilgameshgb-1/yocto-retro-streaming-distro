SUMMARY = "Flask Web UI to launch RetroArch games"
DESCRIPTION = "A lightweight Python Flask application that starts on boot and allows game launching via a web browser."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} += " \
    python3-flask \
    python3-modules \
    python3-core \
    python3-evdev \
    procps \
"

SRC_URI = " \
    file://app.py \
    file://virtual-pad.py \
    file://retro-web.service \
    file://virtual-pad.service \
    file://templates/index.html \
    file://templates/games.html \
    file://templates/play.html \
    file://templates/controller.html \
    file://static/ \
"

# Set S to WORKDIR
S = "${WORKDIR}"

# Inherit systemd to handle the background service logic
inherit systemd

SYSTEMD_SERVICE:${PN} = "retro-web.service virtual-pad.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}/home/root/webui/templates
    install -d ${D}/home/root/webui/static
    install -d ${D}${systemd_system_unitdir}

    install -m 0755 ${S}/app.py         ${D}/home/root/webui/
    install -m 0755 ${S}/virtual-pad.py ${D}/home/root/webui/

    install -m 0644 ${S}/templates/index.html      ${D}/home/root/webui/templates/
    install -m 0644 ${S}/templates/games.html      ${D}/home/root/webui/templates/
    install -m 0644 ${S}/templates/play.html       ${D}/home/root/webui/templates/
    install -m 0644 ${S}/templates/controller.html ${D}/home/root/webui/templates/

    cp -r ${S}/static/* ${D}/home/root/webui/static/
    chown -R root:root ${D}/home/root/webui/static

    install -m 0644 ${WORKDIR}/retro-web.service   ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/virtual-pad.service ${D}${systemd_system_unitdir}
}

# Ensure Yocto packages the custom /home/root directory
FILES:${PN} += " \
    /home/root/webui \
    ${systemd_system_unitdir}/retro-web.service \
    ${systemd_system_unitdir}/virtual-pad.service \
"