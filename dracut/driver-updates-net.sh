#!/bin/sh
[ -e /tmp/DD-net ] || return 0

command -v getarg >/dev/null || . /lib/dracut-lib.sh
. /lib/anaconda-lib.sh

if [ -n "$(ls /tmp/DD-net)" ]; then
    # Run the systemd service for network drivers
    tty=$(find_tty)

    # Update module list so we don't unload the network driver
    cat /proc/modules > /tmp/dd_modules

    info "Starting Network Driver Update Disk Service on $tty"
    systemctl start driver-updates-net@$tty.service
    status=$(systemctl -p ExecMainStatus show driver-updates-net@$tty.service)
    info "Network DD status=$status"
    rm -rf /tmp/DD-net
fi
