SUMMARY = "my image for retro emulator recipe"
LICENSE = "MIT"

require recipes-core/images/core-image-base.bb

# Features and Packages
IMAGE_FEATURES += "ssh-server-dropbear"
IMAGE_INSTALL += " \
    vsftpd \
    retroarch \
    mgba-libretro \
    custom-roms \
    alsa-utils \
    alsa-plugins \
    python3-flask \
    python3-modules \
    retro-web-ui \
    bash \
    procps \
"