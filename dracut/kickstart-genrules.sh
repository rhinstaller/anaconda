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
        wait_for_kickstart
    ;;
    bd) # bd:<dev>:<path> - biospart (TODO... if anyone uses this anymore)
        warn "inst.ks: can't get kickstart - biospart (bd:) isn't supported yet"
    ;;
esac
