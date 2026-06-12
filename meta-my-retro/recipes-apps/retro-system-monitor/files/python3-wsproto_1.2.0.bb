SUMMARY = "Websocket protocol implementation"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=f268f7734139e6a32d665f24f5a31c19"

inherit pypi setuptools3

SRC_URI[sha256sum] = "c6563e3d64c08e50b730f0f354f9a03222a012a64c4c81121d5a3632f05a06ef"

RDEPENDS:${PN} += " \
    python3-core \
    python3-h11 \
"