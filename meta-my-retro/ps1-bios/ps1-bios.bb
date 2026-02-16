SUMMARY = "PlayStation 1 BIOS files for RetroArch"
LICENSE = "CLOSED" # BIOS files are proprietary

SRC_URI = " \
    file://scph5501.bin \
"

S = "${WORKDIR}"

do_install() {
    install -d ${D}/usr/share/retroarch/bios
    install -m 0644 ${S}/scph5501.bin ${D}/usr/share/retroarch/bios/
}

FILES:${PN} += "/usr/share/retroarch/bios/*.bin"