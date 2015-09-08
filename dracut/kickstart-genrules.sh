#!/bin/sh
# generate udev rules for fetching kickstarts.

. /lib/anaconda-lib.sh

case "${kickstart%%:*}" in
    http|https|ftp|nfs)
        # handled by fetch-kickstart-net in the online hook
        wait_for_kickstart
    ;;
    cdrom|hd) # cdrom, cdrom:<path>, hd:<dev>:<path>
        splitsep ":" "$kickstart" kstype ksdev kspath
        if [ "$kstype" = "cdrom" ] && [ -z "$kspath" ]; then
            kspath="$ksdev"
            when_any_cdrom_appears \
                fetch-kickstart-disk \$env{DEVNAME} "$kspath"
        else
            ksdev=$(disk_to_dev_path $ksdev)
            when_diskdev_appears "$ksdev" \
                fetch-kickstart-disk \$env{DEVNAME} "$kspath"
        fi
        # "cdrom:" also means "wait forever for kickstart" because rhbz#1168902
        if [ "$kstype" = "cdrom" ]; then
            # if we reset main_loop to 0 every loop, we never hit the timeout.
            # (see dracut's dracut-initqueue.sh for details on the mainloop)
            echo "main_loop=0" > "$hookdir/initqueue/ks-cdrom-wait-forever.sh"
        fi
        wait_for_kickstart
    ;;
    bd) # bd:<dev>:<path> - biospart (TODO... if anyone uses this anymore)
        warn "inst.ks: can't get kickstart - biospart (bd:) isn't supported yet"
    ;;
    "")
        if [ -z "$kickstart" -a -z "$(getarg ks= inst.ks=)" ]; then
            when_diskdev_appears $(disk_to_dev_path LABEL=OEMDRV) \
                fetch-kickstart-disk \$env{DEVNAME} "/ks.cfg"
        fi
    ;;
esac
