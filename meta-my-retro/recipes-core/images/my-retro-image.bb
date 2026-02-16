SUMMARY = "my image for retro emulator recipe"
LICENSE = "MIT"

require recipes-core/images/core-image-base.bb

# Features and Packages
IMAGE_FEATURES += "ssh-server-dropbear"
IMAGE_INSTALL += " \
    vsftpd \
    gdb \
    retroarch \
    mgba-libretro \
    mupen64plus-libretro \
    ppsspp-libretro \
    custom-roms \
    alsa-utils \
    alsa-plugins \
    python3-flask \
    python3-modules \
    retro-web-ui \
    bash \
    procps \
    bluez5 \
    pi-bluetooth \
    linux-firmware-rpidistro-bcm43430 \
    usbutils \
    retroarch-autoconfig \
    auto-pair \
    networkmanager \
    networkmanager-nmcli \
    linux-firmware-rpidistro-bcm43455 \
    dnsmasq \
    hotspot-config \
"

# dolphin-libretro \
# glibc-utils \