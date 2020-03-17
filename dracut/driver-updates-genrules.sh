#!/bin/bash

command -v wait_for_dd >/dev/null || . /lib/anaconda-lib.sh

# Don't leave initqueue until we've finished with the requested dd stuff
[ -f /tmp/dd_todo ] && wait_for_dd

DD_OEMDRV=""
if [ -f /tmp/dd_interactive ]; then
    initqueue --onetime --settled --name zz_dd_interactive \
        systemctl start driver-updates@$(find_tty).service
else
    # Only process OEMDRV in non-interactive mode
    DD_OEMDRV="LABEL=OEMDRV"
fi

DD_DISKS=""
if [ -f /tmp/dd_disk ]; then
    DD_DISKS=$(cat /tmp/dd_disk)
else
    debug_msg "/tmp/dd_disk file was not created"
fi

# Run driver-updates for LABEL=OEMDRV and any other requested disk/image
for dd in $DD_OEMDRV $DD_DISKS; do
    # ..is this actually a disk image that already exists inside initramfs?
    if [ -f $dd ]; then
        # if so, no need to wait for udev - add it to initqueue now
        initqueue --onetime --name dd_initrd \
            driver-updates --disk $dd $dd
    # otherwise, tell udev to do driver-updates when the device appears
    else
        # replace '\' with '\\' for udev rules
        # otherwise '\' will be lost during the command execution (required for \x20)
        dd_whitespace_fix=${dd//\\/\\\\}
        # this is a disk with path to specific RPM file on it
        if [ "${dd##*.}" = "rpm" ]; then
            splitsep ":" "$dd" dd_type dd_dev dd_path
            when_diskdev_appears "$(disk_to_dev_path $dd_type)" \
                driver-updates --disk $dd_whitespace_fix \$devnode $dd_dev
        else
            when_diskdev_appears "$(disk_to_dev_path $dd)" \
                driver-updates --disk $dd_whitespace_fix \$devnode
        fi
    fi
done

# force us to wait at least until we've settled at least once
echo '> /tmp/settle.done' > $hookdir/initqueue/settled/settle_done.sh
echo '[ -f /tmp/settle.done ]' > $hookdir/initqueue/finished/wait_for_settle.sh

# NOTE: dd_net is handled by fetch-driver-net.sh
