SUMMARY = "First-boot service to create and mount a movies partition from unallocated SD card space"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://movies-storage-init.sh \
    file://movies-storage-init.service \
"

# sfdisk: util-linux-sfdisk; mkfs.ext4: e2fsprogs-mke2fs; blockdev: util-linux-blockdev
RDEPENDS:${PN} = " \
    parted \
    util-linux-partx \
    e2fsprogs-resize2fs \
"

inherit systemd

SYSTEMD_SERVICE:${PN} = "movies-storage-init.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    # Install the init script
    install -d ${D}/usr/lib
    install -m 0755 ${WORKDIR}/movies-storage-init.sh ${D}/usr/lib/movies-storage-init.sh

    # Install the systemd service
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/movies-storage-init.service \
        ${D}${systemd_system_unitdir}/movies-storage-init.service

    # Create the mount point in the rootfs
    install -d ${D}/home/root/movies
}

FILES:${PN} = " \
    /usr/lib/movies-storage-init.sh \
    ${systemd_system_unitdir}/movies-storage-init.service \
    /home/root/movies \
"
