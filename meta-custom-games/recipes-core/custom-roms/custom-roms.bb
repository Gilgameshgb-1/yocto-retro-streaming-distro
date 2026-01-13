SUMMARY = "Custom ROMs for RetroArch"
LICENSE = "CLOSED"

SRC_URI = " \
    file://GXDuelAcademy.gba \
"

S = "${WORKDIR}"

do_install() {
    # Already provided folder by retroarch by just in case
    # of any random reason the directory is missing we
    # provide a location for the ROMs (GBA only for now)
    install -d ${D}/usr/games/
    
    # Ensure file can be seen write/read permissions
    install -m 0644 ${S}/GXDuelAcademy.gba ${D}/usr/games/
}

# Tell Yocto that these files belong to the package
FILES:${PN} += "/usr/games/GXDuelAcademy.gba"