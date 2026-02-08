SUMMARY = "Custom ROMs for RetroArch"
LICENSE = "CLOSED"

SRC_URI = " \
    file://GXDuelAcademy.gba \
    file://DragonBall2.gba \
    file://Medabots.gba \
    file://MetroidFusion.gba \
"

S = "${WORKDIR}"

do_install() {
    # Already provided folder by retroarch by just in case
    # of any random reason the directory is missing we
    # provide a location for the ROMs (GBA only for now)
    install -d ${D}/usr/games/gba/
    
    # Ensure files can be seen write/read permissions (GBA)
    install -m 0644 ${S}/GXDuelAcademy.gba ${D}/usr/games/gba/
    install -m 0644 ${S}/DragonBall2.gba ${D}/usr/games/gba/
    install -m 0644 ${S}/Medabots.gba ${D}/usr/games/gba/
    install -m 0644 ${S}/MetroidFusion.gba ${D}/usr/games/gba/
}

# Tell Yocto that these files belong to the package
FILES:${PN} += "/usr/games/gba/"