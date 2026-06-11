#!/bin/sh

STATUS=$(/usr/bin/netbird status)

if echo "$STATUS" | grep -q "Connected"; then
    echo "NetBird is already connected."
    exit 0
else
    echo "Enrolling device into NetBird mesh..."
    /usr/bin/netbird up --setup-key <NETBIRD_SETUP_KEY>
fi