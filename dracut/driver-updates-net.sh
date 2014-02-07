#!/bin/sh
[ -e /tmp/DD-net ] || return 0

command -v getarg >/dev/null || . /lib/dracut-lib.sh
. /lib/anaconda-lib.sh

if [ -n "$(ls /tmp/DD-net)" ]; then
    start_driver_update "Network Driver Update Disk"
    rm -rf /tmp/DD-net
fi
