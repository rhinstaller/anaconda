#!/bin/sh
# Copy over dhclient config files to the anaconda environment

. /lib/anaconda-lib.sh

[ -d /etc/dhcp ] && copytree /etc/dhcp /run/initramfs/state/etc/dhcp/
[ -f /etc/dhclient.conf ] && cp /etc/dhclient.conf /run/initramfs/state/etc/
