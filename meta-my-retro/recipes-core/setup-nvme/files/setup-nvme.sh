#!/bin/sh
# setup-nvme.sh — Prepare the NVMe SSD as /games and /movies.
#
# The SSD itself is the source of truth, not a flag file on the SD card.
# The old version keyed off /var/lib/nvme-initialized alone, so every
# reflash of the SD card reformatted the SSD on first boot. Now:
#
#   * --force                          -> wipe, partition and format
#   * "games" and "movies" labels found -> keep the data, just mount them
#   * drive completely blank            -> partition and format it
#   * anything else                     -> leave it untouched and say so
#
# Usage: setup-nvme.sh [--dry-run | --force]
#   --dry-run  print what would happen, change nothing
#   --force    wipe the drive even if it holds data
set -e

DRIVE="/dev/nvme0n1"
FLAG="/var/lib/nvme-initialized"

MODE=normal
case "$1" in
    "")        ;;
    --dry-run) MODE=dry ;;
    --force)   MODE=force ;;
    *)         echo "usage: $0 [--dry-run | --force]"; exit 2 ;;
esac

run() {
    if [ "$MODE" = dry ]; then
        echo "  would run: $*"
    else
        "$@"
    fi
}

has_label() {
    blkid | grep -q "^${DRIVE}p[0-9]*: .*LABEL=\"$1\""
}

is_blank() {
    # No partitions and no filesystem written straight onto the disk.
    ! grep -q "${DRIVE#/dev/}p[0-9]" /proc/partitions && ! blkid | grep -q "^${DRIVE}:"
}

format_drive() {
    SECTORS=$(cat /sys/block/nvme0n1/size)
    SIZE_GB=$(( SECTORS / 2 / 1024 / 1024 ))
    GAMES_END_GB=$(( SIZE_GB * 20 / 100 ))
    echo "  p1 /games  : 1MB -> ${GAMES_END_GB}GB"
    echo "  p2 /movies : ${GAMES_END_GB}GB -> 100%"
    run parted -s "$DRIVE" mklabel gpt
    run parted -s "$DRIVE" mkpart games  ext4 1MB "${GAMES_END_GB}GB"
    run parted -s "$DRIVE" mkpart movies ext4 "${GAMES_END_GB}GB" 100%
    run partprobe "$DRIVE"
    [ "$MODE" = dry ] || sleep 2
    run mkfs.ext4 -F -L games  "${DRIVE}p1"
    run mkfs.ext4 -F -L movies "${DRIVE}p2"
}

add_fstab() {
    grep -q "^LABEL=$1[[:space:]]" /etc/fstab && return 0
    if [ "$MODE" = dry ]; then
        echo "  would add to /etc/fstab: LABEL=$1  $2"
    else
        echo "LABEL=$1  $2  ext4  defaults,nofail  0  2" >> /etc/fstab
    fi
}

mount_if_needed() {
    grep -q " $1 " /proc/mounts && { echo "  $1 already mounted"; return 0; }
    run mount "$1"
}

echo "=== NVMe storage setup ($MODE) ==="

if [ ! -b "$DRIVE" ]; then
    echo "ERROR: $DRIVE not found - is the SSD connected and detected?"
    exit 1
fi

if [ "$MODE" = force ]; then
    echo "--force: wiping $DRIVE"
    format_drive
elif has_label games && has_label movies; then
    echo "Found existing games and movies filesystems - keeping their data."
elif is_blank; then
    echo "$DRIVE is blank - partitioning and formatting."
    format_drive
else
    echo "$DRIVE holds partitions, but not ones labelled games and movies:"
    blkid | grep "^${DRIVE}" || grep "${DRIVE#/dev/}" /proc/partitions || true
    echo "Leaving it untouched. To wipe it and start over: $0 --force"
    exit 1
fi

run mkdir -p /games /movies
add_fstab games  /games
add_fstab movies /movies
mount_if_needed /games
mount_if_needed /movies
run chmod 777 /games /movies

run mkdir -p "$(dirname "$FLAG")"
run touch "$FLAG"

echo "Done."
[ "$MODE" = dry ] || df -h /games /movies
