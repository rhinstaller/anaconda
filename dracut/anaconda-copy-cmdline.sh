#!/bin/sh
# Copy over cmdline(.d) files from the initrd to /run before pivot
mkdir -p /run/install/cmdline.d
cp /etc/cmdline.d/* /run/install/cmdline.d/
cp /etc/cmdline /run/install/
