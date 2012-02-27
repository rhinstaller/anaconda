#!/bin/sh
# generate udev rules for fetching kickstarts.

case "${kickstart%%:*}" in
    file|path) # file:<path> (we accept path: but that's deprecated)
        splitsep ":" "$kickstart" kstype kspath
        if [ -f "$kspath" ]; then
            cp $kspath /tmp/ks.cfg
            /sbin/parse-kickstart $kspath >> /etc/cmdline.d/80kickstart.conf
            unset CMDLINE
        else
            warn "inst.ks='$kickstart'"
            warn "can't find $kspath!"
        fi
    ;;
    cdrom|hd|bd) # cdrom:<dev>, hd:<dev>:<path>, bd:<dev>:<path>
        splitsep ":" "$kickstart" kstype ksdev kspath
        ksdev=$(disk_to_dev_path $ksdev)
        if [ "$kstype" = "bd" ]; then # TODO FIXME: no biospart support yet
            warn "inst.ks='$kickstart'"
            warn "can't get kickstart: biospart isn't supported yet"
            ksdev=""
        fi
        [ -n "$ksdev" ] && \
        when_diskdev_appears "$ksdev" \
            "/sbin/fetch-kickstart-disk \$env{DEVNAME} $kspath"
    ;;
    http|https|ftp|nfs)
        if [ "$ksiface" = "ibft" ]; then # TODO FIXME: ibft
            warn "inst.ks.device=ibft isn't supported yet!"
            ksiface=""
        fi
        when_netdev_online "${ksiface:-any}" \
            "/sbin/fetch-kickstart-net \$env{INTERFACE} $kickstart"
    ;;
esac

# Make sure we wait for the kickstart to be fetched
if [ -n "$kickstart" ]; then
    echo "[ -e /tmp/ks.cfg.done ]" > $hookdir/initqueue/finished/kickstart.sh
