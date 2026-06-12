#!/bin/sh

STATUS=$(/usr/bin/netbird status)

if echo "$STATUS" | grep -q "Connected"; then
    echo "NetBird is already connected."
    exit 0
fi

if [ -f /etc/netbird-token ]; then
    TOKEN=$(cat /etc/netbird-token)
    echo "Enrolling device into NetBird mesh..."
    /usr/bin/netbird up --setup-key "$TOKEN"
else
    echo "Error: NetBird token configuration file missing at /etc/netbird-token"
    exit 1
fi