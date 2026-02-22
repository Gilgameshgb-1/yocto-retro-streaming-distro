SUMMARY = "BIOS files for Flycast (Dreamcast)"
LICENSE = "CLOSED"

SRC_URI = " \
    file://dc_boot.bin \
    file://dc_flash.bin \
"

S = "${WORKDIR}"

do_install() {
    install -d ${D}/usr/share/retroarch/bios/dc

    install -m 0644 ${S}/dc_boot.bin ${D}/usr/share/retroarch/bios/dc/
    install -m 0644 ${S}/dc_flash.bin ${D}/usr/share/retroarch/bios/dc/
}

FILES:${PN} += "/usr/share/retroarch/bios/dc/"