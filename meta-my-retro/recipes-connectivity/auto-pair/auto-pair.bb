SUMMARY = "Pre-pair and Auto-connect DualSense Controller"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Ensure we have the python helper for runtime
RDEPENDS:${PN} += "python3-core python3-pexpect bluez5"

inherit systemd

SRC_URI = " \
    file://info \
    file://attributes \
    file://auto-pair.py \
    file://99-ps5-controller.rules \
"

S = "${WORKDIR}"

ADAPTER_MAC = "2C:CF:67:AD:38:FB" 
CONTROLLER_MAC = "14:3A:9A:72:C1:B4"

do_install() {
    #Install the "Pre-Bonded" keys (My PS5 dualsense) directly into the BlueZ stack
    install -d ${D}${localstatedir}/lib/bluetooth/${ADAPTER_MAC}/${CONTROLLER_MAC}
    install -m 0600 ${WORKDIR}/info ${D}${localstatedir}/lib/bluetooth/${ADAPTER_MAC}/${CONTROLLER_MAC}/info
    install -m 0600 ${WORKDIR}/attributes ${D}${localstatedir}/lib/bluetooth/${ADAPTER_MAC}/${CONTROLLER_MAC}/attributes

    #Install the Python script 1st version for testing autoconnect
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/auto-pair.py ${D}${bindir}/auto-pair.py
}

do_install:append() {
    install -d ${D}${sysconfdir}/udev/rules.d
    install -m 0644 ${WORKDIR}/99-ps5-controller.rules ${D}${sysconfdir}/udev/rules.d/
}

FILES:${PN} += " \
    ${localstatedir}/lib/bluetooth/* \
    ${bindir}/auto-pair.py \
"