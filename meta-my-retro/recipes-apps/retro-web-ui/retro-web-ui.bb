SUMMARY = "Flask Web UI to launch RetroArch games"
DESCRIPTION = "A lightweight Python Flask application that starts on boot and allows game launching via a web browser."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Fixed RDEPENDS: python3-modules includes subprocess, os, and shell logic
RDEPENDS:${PN} += " \
    python3-flask \
    python3-modules \
    python3-core \
    procps \
"

SRC_URI = " \
    file://app.py \
    file://retro-web.service \
    file://templates/index.html \
    file://templates/games.html \
    file://static/ \
"

# Set S to WORKDIR
S = "${WORKDIR}"

# Inherit systemd to handle the background service logic
inherit systemd

SYSTEMD_SERVICE:${PN} = "retro-web.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    # 1. Create the destination directories in the image filesystem
    install -d ${D}/home/root/webui/templates
    install -d ${D}/home/root/webui/static
    install -d ${D}${systemd_system_unitdir}
    
    # 2. Install the application files from the build workspace
    # Using -m 0755 for scripts (executable) and 0644 for configs/html
    install -m 0755 ${S}/app.py ${D}/home/root/webui/
    install -m 0644 ${S}/templates/index.html ${D}/home/root/webui/templates/
    install -m 0644 ${S}/templates/games.html ${D}/home/root/webui/templates/
    
    cp -r ${S}/static/* ${D}/home/root/webui/static/
    chown -R root:root ${D}/home/root/webui/static

    # 3. Install the systemd unit file
    install -m 0644 ${WORKDIR}/retro-web.service ${D}${systemd_system_unitdir}
}

# Ensure Yocto packages the custom /home/root directory
FILES:${PN} += " \
    /home/root/webui \
    ${systemd_system_unitdir}/retro-web.service \
"