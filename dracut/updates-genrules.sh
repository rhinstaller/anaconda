#!/bin/sh
# generate udev rules for fetching updates

. /lib/anaconda-lib.sh

# NOTE: anac_updates is a special variable holding Anaconda-style URL for updates.img
# shellcheck disable=SC2154
updates=$anac_updates
[ -n "$updates" ] || return
case $updates in
    # updates=<url>: handled by livenet's fetch-liveupdate.sh
    http*|ftp*|nfs*)
        wait_for_updates
    ;;
    # updates=<disk>:<path>
    #   <disk> is sdb, /dev/sdb, LABEL=xxx, UUID=xxx
    #   <path> defaults to /updates.img if missing
    *)
        # accept hd:<dev>:<path> (or cdrom:<dev>:<path>)
        updates=${updates#hd:}; updates=${updates#cdrom:}
        splitsep ":" "$updates" dev path
        # NOTE: the path variable is set by splitsep
        # shellcheck disable=SC2154
        dev=$(disk_to_dev_path $dev)
        when_diskdev_appears $dev fetch-updates-disk "\$env{DEVNAME}" $path
        wait_for_updates
    ;;
esac
