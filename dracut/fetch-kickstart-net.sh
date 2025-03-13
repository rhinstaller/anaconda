#!/bin/bash
# fetch-kickstart-net - fetch kickstart file from the network.
# runs from the "initqueue/online" hook whenever a net interface comes online

# initqueue/online hook passes interface name as $1
netif="$1"

# do not use 'lo' device
[ "$netif" == "lo" ] && return 0

# we already processed the kickstart - exit
[ -e /tmp/ks.cfg.done ] && return 0

# no kickstart requested - exit
[ -n "$kickstart" ] || return 0

# user requested a specific device, but this isn't it - exit
[ -n "$ksdevice" ] && [ "$ksdevice" != "$netif" ] && return 0

command -v getarg >/dev/null || . /lib/dracut-lib.sh
. /lib/url-lib.sh
. /lib/anaconda-lib.sh

# Find locations to the kickstart files.
locations=""

case $kickstart in
    nfs*)
        # Construct URL for nfs:auto.
        if [ "$kickstart" = "nfs:auto" ]; then
            # Construct kickstart URL from dhcp info.
            # Filename is dhcp 'filename' option, or '/kickstart/' if missing.
            filename="/kickstart/"
            . "/tmp/net.$netif.dhcpopts"
            # Server is next_server, or the dhcp server itself if missing.
            server="${new_next_server:-$new_dhcp_server_identifier}"
            kickstart="nfs:$server:$filename"
        fi

        # URLs that end in '/' get '$IP_ADDR-kickstart' appended.
        if [[ $kickstart == nfs*/ ]]; then
            kickstart="${kickstart}${new_ip_address:=$(ip -4 addr show "${netif}" | sed -n -e '/^ *inet / s|^ *inet \([^/]\+\)/.*$|\1|p')}-kickstart"
        fi

        # Use the prepared url.
        locations="$kickstart"
    ;;
    http*|ftp*)
        # Use the location from the variable.
        locations="$kickstart"
    ;;
    urls)
        # Use the locations from the file.
        # We will try them one by one until we succeed.
        locations="$(</tmp/ks_urls)"
    ;;
    cdrom*|hd*)
        # do not print the unknown network kickstart in case the local kickstart file
        # is processed in the fetch-kickstart-disk script
        return 0
    ;;
    *)
        warn_critical "unknown network kickstart URL: $kickstart"
        return 1
    ;;
esac

# If we're doing sendmac, we need to run after anaconda-ks-sendheaders.sh
if getargbool 0 inst.ks.sendmac kssendmac; then
    newjob=$hookdir/initqueue/settled/fetch-ks-${netif}.sh
else
    newjob=$hookdir/initqueue/fetch-ks-${netif}.sh
fi

# Create a new job.
cat > "$newjob" <<__EOT__
. /lib/url-lib.sh
. /lib/anaconda-lib.sh
locations="$locations"

info "anaconda: kickstart locations are: \$locations"

for kickstart in \$locations; do
    info "anaconda: fetching kickstart from \$kickstart"

    if fetch_url "\$kickstart" /tmp/ks.cfg; then
        info "anaconda: successfully fetched kickstart from \$kickstart"
        parse_kickstart /tmp/ks.cfg
        run_kickstart
        break
    else
        warn_critical "anaconda: failed to fetch kickstart from \$kickstart"
    fi
done
rm \$job # remove self from initqueue
__EOT__
