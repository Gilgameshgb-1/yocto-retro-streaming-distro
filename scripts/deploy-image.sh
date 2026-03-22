#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_DIR="$PROJECT_ROOT/build/tmp/deploy/images/raspberrypi5"
DEST_WIN="/mnt/c/Users/bmwfa/Downloads"

# Use the symlink (always points to latest build)
WIC_BZ2_LINK="$IMAGE_DIR/my-retro-image-raspberrypi5.rootfs.wic.bz2"

if [ ! -e "$WIC_BZ2_LINK" ]; then
    echo "Error: No image found at $WIC_BZ2_LINK"
    exit 1
fi

FILENAME="$(basename "$WIC_BZ2_LINK")"
WIC_FILENAME="${FILENAME%.bz2}"

echo "==> Copying $FILENAME to project root..."
cp "$WIC_BZ2_LINK" "$PROJECT_ROOT/$FILENAME"

echo "==> Decompressing..."
bunzip2 -f "$PROJECT_ROOT/$FILENAME"

echo "==> Copying $WIC_FILENAME to $DEST_WIN ..."
cp "$PROJECT_ROOT/$WIC_FILENAME" "$DEST_WIN/$WIC_FILENAME"

echo "==> Cleaning up .wic from project root..."
rm -f "$PROJECT_ROOT/$WIC_FILENAME"

echo ""
echo "Done! Flash with:"
echo "  dd if=$DEST_WIN/$WIC_FILENAME of=/dev/sdX bs=4M status=progress"
