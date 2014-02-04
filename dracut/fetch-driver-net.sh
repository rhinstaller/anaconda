#!/bin/bash
# fetch-driver-net - fetch driver from the network.
# runs from the "initqueue/online" hook whenever a net interface comes online

# initqueue/online hook passes interface name as $1
netif="$1"

# We already processed the dd_args - exit
[ -e /tmp/dd_net.done ] && return 0

command -v getarg >/dev/null || . /lib/dracut-lib.sh
dd_args="$(getargs dd= inst.dd=)"
[ -n "$dd_args" ] || return 0

. /lib/url-lib.sh
dd_repo=/tmp/DD-net/
for dd in $dd_args; do
    case "${dd%%:*}" in
        http|https|ftp|nfs|nfs4)
            [ -e "$dd_repo" ] || mkdir -p $dd_repo
            info "Fetching driver from $dd"
            if driver=$(fetch_url "$dd"); then
                mv "$driver" $dd_repo
            else
                warn "Failed to fetch driver from $dd"
            fi
            ;;
    esac
done
echo > /tmp/dd_net.done
