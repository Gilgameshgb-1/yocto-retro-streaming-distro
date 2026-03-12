SUMMARY = "WiFi Hotspot for my-retro-pi"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://Hotspot.nmconnection \
           file://retro-firewall \
          "

S = "${WORKDIR}"

RDEPENDS:${PN} = "iptables"

FILES:${PN} = " \
    ${sysconfdir}/NetworkManager/system-connections/Hotspot.nmconnection \
    ${sysconfdir}/NetworkManager/dispatcher.d/99-retro-firewall \
"

do_install() {
    install -d ${D}${sysconfdir}/NetworkManager/system-connections
    install -m 0600 ${S}/Hotspot.nmconnection ${D}${sysconfdir}/NetworkManager/system-connections/Hotspot.nmconnection

    # NM dispatcher script: opens ports 5000+5001 when the hotspot comes up
    install -d ${D}${sysconfdir}/NetworkManager/dispatcher.d
    install -m 0755 ${S}/retro-firewall ${D}${sysconfdir}/NetworkManager/dispatcher.d/99-retro-firewall
}

FILES:${PN} += "${sysconfdir}/NetworkManager/system-connections/*"