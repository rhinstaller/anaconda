#!/bin/bash
# apply-dracut-updates.sh - run a well-known script injected into initramfs

echo "Applying anaconda dracut updates: '/upd-dracut.sh d'"
/upd-dracut.sh d
