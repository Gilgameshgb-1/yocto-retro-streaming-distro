# Try this to fix "Task (/home/faris/poky-rpi/meta-retro/recipes-retroarch/retroarch/retroarch_1.18.0.bb:do_configure) failed with exit code '1'"
PACKAGECONFIG:append = " gles egl kms"

do_install:append() {
    # Fix up audio issues by setting proper driver and refresh rate, don't change the HDMI variant yet
    sed -i 's/audio_driver = .*/audio_driver = "alsa"/' ${D}${sysconfdir}/retroarch.cfg
    sed -i 's/audio_out_rate = .*/audio_out_rate = "48000"/' ${D}${sysconfdir}/retroarch.cfg
}