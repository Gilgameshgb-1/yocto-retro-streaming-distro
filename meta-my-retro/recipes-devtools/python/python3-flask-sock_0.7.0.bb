SUMMARY = "WebSocket support for Flask applications"
HOMEPAGE = "https://github.com/miguelgrinberg/flask-sock"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=9d272c9fe2437531b5bbecf4fcc82e24"

# This tells BitBake how to build/install the python package
inherit setuptools3

# The official source
SRC_URI = "git://github.com/miguelgrinberg/flask-sock;protocol=https;tag=v0.7.0;branch=main"
S = "${WORKDIR}/git"

RDEPENDS:${PN} += " \
    python3-core \
    python3-flask \
    python3-simple-websocket \
"