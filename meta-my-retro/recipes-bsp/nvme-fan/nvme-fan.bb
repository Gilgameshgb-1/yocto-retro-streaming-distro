SUMMARY = "Speed the Pi 5 fan up when the NVMe SSD gets hot"
DESCRIPTION = "The kernel runs the fan from CPU temperature only. This service \
also watches the NVMe SSD and takes the fan over while the drive is hot."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://nvme-fan.sh \
    file://nvme-fan.service \
"

S = "${WORKDIR}"

inherit systemd allarch

SYSTEMD_SERVICE:${PN} = "nvme-fan.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}${bindir}
    install -d ${D}${systemd_system_unitdir}
    install -m 0755 ${WORKDIR}/nvme-fan.sh ${D}${bindir}/nvme-fan.sh
    install -m 0644 ${WORKDIR}/nvme-fan.service ${D}${systemd_system_unitdir}/nvme-fan.service
}

FILES:${PN} += "${systemd_system_unitdir}/nvme-fan.service"
