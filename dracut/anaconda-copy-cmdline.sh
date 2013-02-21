#!/bin/sh
# Copy over cmdline(.d) files from the initrd to /run before pivot
mkdir -p /run/install/cmdline.d
for f in /etc/cmdline.d/*; do
    [ -e $f ] && cp $f /run/install/cmdline.d/
done
[ -e /etc/cmdline ] && cp /etc/cmdline /run/install/
