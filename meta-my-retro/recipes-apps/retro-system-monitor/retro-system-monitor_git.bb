SUMMARY = "Raspberry Pi 5 Retro System Monitor Ecosystem"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "git://github.com/Gilgameshgb-1/retro-system-monitor-rpi5.git;protocol=https;branch=main \
           file://retro-system-broker.service \
           file://retro-system-producer.service"

SRCREV = "${AUTOREV}"
S = "${WORKDIR}/git"

# Random deps its complaining about, coming from ixwebsocket
DEPENDS += "zlib openssl"

EXTRA_OECMAKE += " \
    -DFETCHCONTENT_FULLY_DISCONNECTED=OFF \
    -DZLIB_LIBRARY=${STAGING_LIBDIR}/libz.so \
    -DZLIB_INCLUDE_DIR=${STAGING_INCDIR} \
    -DOPENSSL_ROOT_DIR=${STAGING_DIR_TARGET}/usr \
    -DOPENSSL_SSL_LIBRARY=${STAGING_LIBDIR}/libssl.so \
    -DOPENSSL_CRYPTO_LIBRARY=${STAGING_LIBDIR}/libcrypto.so \
"

# Inherit both CMake build logic and Systemd service registration
inherit cmake systemd

# Explicitly tell Yocto to allow network access during configuration for libs
EXTRA_OECMAKE += "-DFETCHCONTENT_FULLY_DISCONNECTED=OFF"

do_configure[network] = "1"
do_compile[network] = "1"

SYSTEMD_SERVICE:${PN} = "retro-system-broker.service retro-system-producer.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_compile() {
    # The cmake class automatically handles building the C++ binary inside the ${B} directory
    cmake_do_compile
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/retro-system-monitor ${D}${bindir}/retro-system-monitor

    install -d ${D}/usr/share/retro-system-monitor/webserver
    cp -r ${S}/webserver/* ${D}/usr/share/retro-system-monitor/webserver/
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/retro-system-broker.service ${D}${systemd_unitdir}/system/
    install -m 0644 ${WORKDIR}/retro-system-producer.service ${D}${systemd_unitdir}/system/
}

FILES:${PN} += "/usr/share/retro-system-monitor \
                ${systemd_unitdir}/system/retro-system-broker.service \
                ${systemd_unitdir}/system/retro-system-producer.service"

# These have to be known by the recipe, misleading fact is flask comes included in meta-python
RDEPENDS:${PN} += " \
    python3-core \
    python3-flask \
    python3-flask-sock \
    python3-simple-websocket \
"