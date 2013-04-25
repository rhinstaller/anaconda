#!/bin/bash
# Determine if a Driver Update Disk is present, or inst.dd passed on the cmdline
# and launch the driver update systemd service

# save module state
cat /proc/modules > /tmp/dd_modules

# load all modules
udevadm trigger
udevadm settle

# Look for devices with the OEMDRV label
blkid -t LABEL=OEMDRV > /dev/null
blkid_rc=$?

# dd_args will have been set by parse-anaconda-dd.sh cmdline hook
if [ -n "$dd_args" -o $blkid_rc -eq 0 ]; then
    command -v getarg >/dev/null || . /lib/dracut-lib.sh
    . /lib/anaconda-lib.sh

    tty=$(find_tty)
    # kludge to let kernel spit out some extra info w/o stomping on our UI
    sleep 5

    echo "$dd_args" > /tmp/dd_args
    info "Starting Driver Update Disk Service on $tty"
    systemctl start driver-updates@$tty.service
    status=$(systemctl -p ExecMainStatus show driver-updates@$tty.service)
    info "DD status=$status"
fi

