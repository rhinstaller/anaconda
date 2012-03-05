#!/bin/sh
# generate udev rules for fetching kickstarts.

case "${kickstart%%:*}" in
    file|path) # file:<path> (we accept path: but that's deprecated)
        splitsep ":" "$kickstart" kstype kspath
        if [ -f "$kspath" ]; then
            cp $kspath /tmp/ks.cfg
            parse_kickstart /tmp/ks.cfg
            unset CMDLINE
        else
            warn "inst.ks='$kickstart'"
            warn "can't find $kspath!"
        fi
    ;;
    http|https|ftp|nfs)
        # network module will bring the right interface(s) online, and then..
        when_netdev_online \
            "/sbin/fetch-kickstart-net \$env{INTERFACE} $kickstart"
        wait_for_kickstart
    ;;
    cdrom|hd|bd) # cdrom:<dev>, hd:<dev>:<path>, bd:<dev>:<path>
        splitsep ":" "$kickstart" kstype ksdev kspath
        ksdev=$(disk_to_dev_path $ksdev)
        if [ "$kstype" = "bd" ]; then # TODO FIXME: no biospart support yet
            warn "inst.ks='$kickstart'"
            warn "can't get kickstart: biospart isn't supported yet"
            ksdev=""
        else
            when_diskdev_appears "$ksdev" \
                "/sbin/fetch-kickstart-disk \$env{DEVNAME} $kspath"
            wait_for_kickstart
        fi
    ;;
esac
