#!/bin/bash
# fetch-driver-net - fetch driver from the network.
# runs from the "initqueue/online" hook whenever a net interface comes online

# initqueue/online hook passes interface name as $1
netif="$1"

# No dd_net was requested - exit
[ -f /tmp/dd_net ] || return 0

. /lib/url-lib.sh

while read dd; do
    # If we already fetched this URL, skip it
    grep -Fqx "$dd" /tmp/dd_net.done && continue
    # Otherwise try to fetch it
    info "Fetching driverdisk from $dd"
    if driver=$(fetch_url "$dd"); then
        echo "$dd" >> /tmp/dd_net.done # mark it done so we don't fetch it again
        driver-updates --net "$dd" "$driver"
    else
        warn "Failed to fetch driver from $dd"
    fi
done < /tmp/dd_net
