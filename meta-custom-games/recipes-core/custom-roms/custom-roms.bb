SUMMARY = "Custom ROMs for RetroArch"
LICENSE = "CLOSED"

SRC_URI = " \
    file://gba/GXDuelAcademy.gba \
    file://gba/DragonBall2.gba \
    file://gba/Medabots.gba \
    file://gba/MetroidFusion.gba \
    file://n64/ConkerBadFurDay.z64 \
    file://n64/MarioParty3.z64 \
    file://n64/PokemonStadium.z64 \
    file://n64/SuperMario64.z64 \
    file://psp/MGSPeaceWalker.iso \
"

S = "${WORKDIR}"

do_install() {
    # Already provided folder by retroarch by just in case
    # of any random reason the directory is missing we
    # provide a location for the ROMs (GBA, n64, psp only for now)
    install -d ${D}/usr/games/gba/
    install -d ${D}/usr/games/n64/
    install -d ${D}/usr/games/psp/

    # Ensure files can be seen write/read permissions (GBA, n64, psp)
    install -m 0644 ${S}/gba/*.gba ${D}/usr/games/gba/
    install -m 0644 ${S}/n64/*.z64 ${D}/usr/games/n64/
    # Don't install psp for now (big files)
    # install -m 0644 ${S}/psp/*.iso ${D}/usr/games/psp/
}

# Tell Yocto that these files belong to the package
FILES:${PN} += "/usr/games/gba/"
FILES:${PN} += "/usr/games/n64/"
FILES:${PN} += "/usr/games/psp/"