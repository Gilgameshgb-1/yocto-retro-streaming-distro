SUMMARY = "WiFi Hotspot for my-retro-pi"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://Hotspot.nmconnection"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/NetworkManager/system-connections
    install -m 0600 ${S}/Hotspot.nmconnection ${D}${sysconfdir}/NetworkManager/system-connections/Hotspot.nmconnection
}

FILES:${PN} += "${sysconfdir}/NetworkManager/system-connections/*"