# Try this to fix "Task (/home/faris/poky-rpi/meta-retro/recipes-retroarch/retroarch/retroarch_1.18.0.bb:do_configure) failed with exit code '1'"
PACKAGECONFIG:append = " gles egl kms"

# Are the input drivers and autoconfigs working properly? 

# Patch n64 emulator
SRC_URI += " \
    file://Mupen64Plus-Next.opt \
"

do_install:append() {
    # n64 emu patch for rpi5
    install -d ${D}/root/.config/retroarch/config/Mupen64Plus-Next
    install -m 0644 ${WORKDIR}/Mupen64Plus-Next.opt ${D}/root/.config/retroarch/config/Mupen64Plus-Next.opt

    # Set vulkan as default video_driver
    sed -i 's/^video_driver = .*/video_driver = "vulkan"/' ${D}${sysconfdir}/retroarch.cfg

    # Fix up audio issues by setting proper driver and refresh rate, don't change the HDMI variant yet
    sed -i 's/audio_driver = .*/audio_driver = "alsa"/' ${D}${sysconfdir}/retroarch.cfg
    sed -i 's/audio_out_rate = .*/audio_out_rate = "48000"/' ${D}${sysconfdir}/retroarch.cfg

    # RetroArch attempt to init input_driver
    sed -i 's/^input_driver = .*/input_driver = "udev"/' ${D}${sysconfdir}/retroarch.cfg
    sed -i 's/^joypad_driver = .*/joypad_driver = "udev"/' ${D}${sysconfdir}/retroarch.cfg
    
    # Must point to the proper directory for autoconfig
    sed -i 's|^# *joypad_autoconfig_dir =.*|joypad_autoconfig_dir = "/usr/share/retroarch/autoconfig"|' ${D}${sysconfdir}/retroarch.cfg
    sed -i 's|^joypad_autoconfig_dir = .*|joypad_autoconfig_dir = "/usr/share/retroarch/autoconfig"|' ${D}${sysconfdir}/retroarch.cfg

    # Enable automatic configuration
    sed -i 's/^input_autodetect_enable = .*/input_autodetect_enable = "true"/' ${D}${sysconfdir}/retroarch.cfg
}

FILES:${PN} += "/root/.config/retroarch/*"