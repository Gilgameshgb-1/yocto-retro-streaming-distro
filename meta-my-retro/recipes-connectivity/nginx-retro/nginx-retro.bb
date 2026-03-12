SUMMARY = "nginx reverse proxy + DNS entries for retro.pi and stream.pi"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://retro.conf \
    file://retro-dns.conf \
"

RDEPENDS:${PN} = "nginx dnsmasq"

inherit allarch

do_install() {
    # Drop-in server blocks — default nginx.conf already includes conf.d/*.conf
    install -d ${D}${sysconfdir}/nginx/conf.d
    install -m 0644 ${WORKDIR}/retro.conf ${D}${sysconfdir}/nginx/conf.d/retro.conf

    # dnsmasq drop-in for NetworkManager's shared hotspot dnsmasq instance
    # NM reads /etc/NetworkManager/dnsmasq-shared.d/ for AP mode
    install -d ${D}${sysconfdir}/NetworkManager/dnsmasq-shared.d
    install -m 0644 ${WORKDIR}/retro-dns.conf ${D}${sysconfdir}/NetworkManager/dnsmasq-shared.d/retro-dns.conf
}

FILES:${PN} = " \
    ${sysconfdir}/nginx/conf.d/retro.conf \
    ${sysconfdir}/NetworkManager/dnsmasq-shared.d/retro-dns.conf \
"
