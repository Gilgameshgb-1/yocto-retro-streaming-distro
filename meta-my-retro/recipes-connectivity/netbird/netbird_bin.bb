SUMMARY = "NetBird VPN Client"
DESCRIPTION = "A WireGuard-based mesh network that connects your devices into a single private network"
HOMEPAGE = "https://netbird.io"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/BSD-3-Clause;md5=550794465ba0ec5312d6919e203a55f9"

PV = "0.71.2"
SRC_URI = "https://github.com/netbirdio/netbird/releases/download/v${PV}/netbird_${PV}_linux_arm64.tar.gz \
           file://netbird.service \
           file://netbird-setup.sh \
           file://netbird-token.txt"

SRC_URI[sha256sum] = "0eeb07e4ce6d5e8c472228e795d2276c90ae642e7bf58b44adeb246d30fcd9c1"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "netbird.service"
SYSTEMD_AUTO_ENABLE = "enable"

INSANE_SKIP:${PN} = "already-stripped architecture"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${S}/netbird ${D}${bindir}/netbird

    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${S}/netbird.service ${D}${systemd_unitdir}/system/

    install -m 0755 ${S}/netbird-setup.sh ${D}${bindir}/netbird-setup.sh

    install -d ${D}${sysconfdir}
    install -m 0600 ${S}/netbird-token.txt ${D}${sysconfdir}/netbird-token
}

FILES:${PN} += "${systemd_unitdir}/system/netbird.service \
                ${bindir}/netbird-setup.sh \
                ${sysconfdir}/netbird-token"