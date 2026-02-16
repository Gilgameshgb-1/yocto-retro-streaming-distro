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
    file://psp/DBZShinBudokai2.iso \
"

# Some attempts at gamecube games
#    file://gamecube/SuperMarioSunshine.rvz \
#    file://Sys/ \

S = "${WORKDIR}"

do_install() {
    # Already provided folder by retroarch by just in case
    # of any random reason the directory is missing we
    # provide a location for the ROMs (GBA, n64, psp only for now)
    install -d ${D}/usr/games/gba/
    install -d ${D}/usr/games/n64/
    install -d ${D}/usr/games/psp/
    # install -d ${D}/usr/games/gamecube/

    # Ensure files can be seen write/read permissions (GBA, n64, psp, gamecube, ps1)
    install -m 0644 ${S}/gba/*.gba ${D}/usr/games/gba/
    install -m 0644 ${S}/n64/*.z64 ${D}/usr/games/n64/
    # install -m 0644 ${S}/gamecube/*.rvz ${D}/usr/games/gamecube/

    # Don't install psp for now (big files)
    # install -m 0644 ${S}/psp/*.iso ${D}/usr/games/psp/

    # Attempt super mario sunshine
    # install -m 0644 ${S}/gamecube/SuperMarioSunshine.rvz ${D}/usr/games/gamecube/

    # Try this game on psp
    install -m 0644 ${S}/psp/DBZShinBudokai2.iso ${D}/usr/games/psp/


    # More attempts at gamecube
    # install -d ${D}/usr/share/retroarch/bios/dolphin-emu/Sys
    # cp -r ${S}/Sys/* ${D}/usr/share/retroarch/bios/dolphin-emu/Sys/
    
    # Set permissions for the Sys folder so the emulator can read/cache shaders
    # chmod -R 755 ${D}/usr/share/retroarch/bios/dolphin-emu/Sys
}

# Tell Yocto that these files belong to the package
FILES:${PN} += "/usr/games/gba/"
FILES:${PN} += "/usr/games/n64/"
FILES:${PN} += "/usr/games/psp/"
FILES:${PN} += "/usr/games/gamecube/"
FILES:${PN} += "/usr/share/retroarch/bios/dolphin-emu/Sys/"