# Try this to fix "Task (/home/faris/poky-rpi/meta-retro/recipes-retroarch/retroarch/retroarch_1.18.0.bb:do_configure) failed with exit code '1'"
PACKAGECONFIG:append = " gles egl kms"