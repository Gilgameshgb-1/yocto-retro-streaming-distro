#!/bin/sh
# setup-nvme.sh — Partition and mount NVMe as /games and /movies
# Idempotent: exits cleanly if already done.
set -e

DRIVE="/dev/nvme0n1"
FLAG="/var/lib/nvme-initialized"

if [ -f "$FLAG" ]; then
    echo "Already initialised. Nothing to do."
    exit 0
fi

if [ ! -b "$DRIVE" ]; then
    echo "ERROR: $DRIVE not found."
    exit 1
fi

SECTORS=$(cat /sys/block/nvme0n1/size)
SIZE_GB=$(( SECTORS / 2 / 1024 / 1024 ))
GAMES_END_GB=$(( SIZE_GB * 20 / 100 ))

echo "=== NVMe Storage Init ==="
echo "Drive : $DRIVE  (${SIZE_GB} GB)"
echo "  p1 /games  : 1MB → ${GAMES_END_GB}GB"
echo "  p2 /movies : ${GAMES_END_GB}GB → 100%"
echo ""
# Wipe and repartition
parted -s $DRIVE mklabel gpt
parted -s $DRIVE mkpart games  ext4 1MB ${GAMES_END_GB}GB
parted -s $DRIVE mkpart movies ext4 ${GAMES_END_GB}GB 100%

sleep 2

echo "Formatting ..."
mkfs.ext4 -F -L games  ${DRIVE}p1
mkfs.ext4 -F -L movies ${DRIVE}p2

mkdir -p /games /movies

# fstab — use labels so no PARTUUID lookup needed
sed -i '\|/games|d; \|/movies|d' /etc/fstab
echo "LABEL=games   /games   ext4  defaults,nofail  0  2" >> /etc/fstab
echo "LABEL=movies  /movies  ext4  defaults,nofail  0  2" >> /etc/fstab

echo "Mounting ..."
mount /games
mount /movies
chmod 777 /games /movies

mkdir -p /var/lib
touch $FLAG

echo ""
echo "============================================"
echo " Done!"
echo "============================================"
df -h /games /movies
