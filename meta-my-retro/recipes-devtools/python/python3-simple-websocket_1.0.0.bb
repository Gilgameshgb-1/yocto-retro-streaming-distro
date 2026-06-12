SUMMARY = "Simple WebSocket server and client for Python"
HOMEPAGE = "https://github.com/miguelgrinberg/simple-websocket"
LICENSE = "MIT"
# Swap in the verified MD5 hash
LIC_FILES_CHKSUM = "file://LICENSE;md5=9d272c9fe2437531b5bbecf4fcc82e24"

inherit pypi setuptools3

RDEPENDS:${PN} += " \
    python3-core \
    python3-io \
    python3-wsproto \
"

SRC_URI[sha256sum] = "17d2c72f4a2bd85174a97e3e4c88b01c40c3f81b7b648b0cc3ce1305968928c8"