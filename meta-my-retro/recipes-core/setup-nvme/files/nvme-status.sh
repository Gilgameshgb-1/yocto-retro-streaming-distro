#!/bin/sh
# nvme-status.sh — Check NVMe state using only busybox-available tools

DRIVE="/dev/nvme0n1"
FLAG="/var/lib/nvme-initialized"

echo "=== NVMe Status ==="
echo ""

# 1. Drive present?
if [ ! -b "$DRIVE" ]; then
    echo "[MISSING] $DRIVE not found"
    echo "  -> Run: dmesg | grep -i nvme"
    exit 1
fi

# Size from sysfs (sectors * 512)
SECTORS=$(cat /sys/block/nvme0n1/size 2>/dev/null || echo 0)
SIZE_GB=$(( SECTORS / 2 / 1024 / 1024 ))
MODEL=$(cat /sys/block/nvme0n1/device/model 2>/dev/null | sed 's/  */ /g' | sed 's/^ //;s/ $//')

echo "[OK] Drive: $DRIVE"
echo "     Model : $MODEL"
echo "     Size  : ${SIZE_GB} GB"
echo ""

# 2. Partitions (from /proc/partitions)
echo "--- Partitions ---"
awk '/nvme0/{printf "  /dev/%s\t%d MB\n", $4, $3/1024}' /proc/partitions
echo ""

# 3. Init flag
echo "--- Init status ---"
if [ -f "$FLAG" ]; then
    echo "[OK] Initialised (flag exists: $FLAG)"
else
    echo "[NOT DONE] Flag not found — run /home/root/setup-nvme.sh"
fi
echo ""

# 4. Mount status
echo "--- Mounts ---"
for mnt in /games /movies; do
    if mount | grep -q " $mnt "; then
        echo "[MOUNTED] $mnt"
        df -h $mnt | awk 'NR==2{printf "           Size: %s  Used: %s  Free: %s  (%s used)\n", $2, $3, $4, $5}'
    else
        echo "[NOT MOUNTED] $mnt"
    fi
done
echo ""

# 5. Write test (only if mounted)
echo "--- Write test ---"
for mnt in /games /movies; do
    if mount | grep -q " $mnt "; then
        if touch $mnt/.write_test 2>/dev/null; then
            rm -f $mnt/.write_test
            echo "[OK] $mnt is writable"
        else
            echo "[FAIL] $mnt is NOT writable"
        fi
    fi
done
echo ""

# 6. fstab
echo "--- /etc/fstab entries ---"
grep -E '/games|/movies' /etc/fstab || echo "(none found)"
echo ""
