#!/bin/sh
# First-boot script: grow the rootfs partition to 42 GB and expand the filesystem to fill it.
set -e

DISK=/dev/mmcblk0
ROOT_PART=${DISK}p2
SENTINEL=/etc/.storage-expanded

# Sentinel as flag file for single init only

if [ -f "$SENTINEL" ]; then
    exit 0
fi

# Extend partition 2 to 42 GB in the partition table.
# parted uses BLKPG_RESIZE_PARTITION ioctl — works on mounted partitions
parted -s "$DISK" resizepart 2 42GB
partx -u "$ROOT_PART" 2>/dev/null || true
resize2fs "$ROOT_PART"

# Ensure the movies directory exists
mkdir -p /home/root/movies

touch "$SENTINEL"

