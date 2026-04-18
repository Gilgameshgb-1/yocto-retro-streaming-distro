SUMMARY = "NVMe storage init scripts and systemd service"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://setup-nvme.sh \
    file://nvme-status.sh \
    file://setup-nvme.service \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "setup-nvme.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}/home/root
    install -d ${D}${systemd_system_unitdir}

    install -m 0755 ${WORKDIR}/setup-nvme.sh   ${D}/home/root/setup-nvme.sh
    install -m 0755 ${WORKDIR}/nvme-status.sh  ${D}/home/root/nvme-status.sh
    install -m 0644 ${WORKDIR}/setup-nvme.service ${D}${systemd_system_unitdir}/setup-nvme.service
}

FILES:${PN} = " \
    /home/root/setup-nvme.sh \
    /home/root/nvme-status.sh \
    ${systemd_system_unitdir}/setup-nvme.service \
"
