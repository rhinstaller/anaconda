#!/bin/bash
# Determine if a Driver Update Disk is present, or inst.dd passed on the cmdline
# and launch the driver update systemd service

# load all modules
udevadm trigger
udevadm settle

# Look for devices with the OEMDRV label
blkid -t LABEL=OEMDRV > /dev/null
blkid_rc=$?

command -v getarg >/dev/null || . /lib/dracut-lib.sh
dd_args="$(getargs dd= inst.dd=)"
if [ -n "$dd_args" -o $blkid_rc -eq 0 ]; then
    command -v getarg >/dev/null || . /lib/dracut-lib.sh
    . /lib/anaconda-lib.sh

    # kludge to let kernel spit out some extra info w/o stomping on our UI
    sleep 5
    echo "$dd_args" > /tmp/dd_args
    start_driver_update "Driver Update Disk"
fi
