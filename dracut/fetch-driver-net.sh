#!/bin/bash
# fetch-driver-net - fetch driver from the network.
# runs from the "initqueue/online" hook whenever a net interface comes online

# initqueue/online hook passes interface name as $1
netif="$1"

# No dd_net was requested - exit
[ -f /tmp/dd_net ] || return 0
DD_NET=$(cat /tmp/dd_net)

. /lib/url-lib.sh

for dd in $DD_NET; do
    # If we already fetched this URL, skip it
    grep -Fqx "$dd" /tmp/dd_net.done && continue
    # Otherwise try to fetch it

    if [[ $dd == *.rpm ]] || [[ $dd == *.iso ]]; then
        # Path in $dd leads to a file
        info "Fetching driverdisk from $dd file"

        if driver=$(fetch_url "$dd"); then
            echo "$dd" >> /tmp/dd_net.done # mark it done so we don't fetch it again
            driver-updates --net "$dd" "$driver"
        else
            warn "Failed to fetch driver from $dd"
        fi

    else
        # Path in $dd leads to a directory

        # Only nfs supports processing of the whole directories
        if [[ $dd == nfs://* ]]; then

            info "Fetching RPM driverdisks from $dd directory"

            # Following variables are set by nfs_to_var:
            local nfs="" server="" path="" options="" mntdir=""
            nfs_to_var "$dd"

            # Obtain mount directory and mount it
            # (new unique name is generated if not already mounted)
            mntdir=$(nfs_already_mounted "$server" "$path")
            if [ -z "$mntdir" ]; then
                mntdir="$(mkuniqdir /run nfs_mnt)"
                mount_nfs "$nfs:$server:$path$(options:+:$options)" "$mntdir"
            fi

            # Get and process all rpm files in the mounted directory
            for rpm_file in $mntdir/*.rpm; do
                # If no file is found bash still loops once
                # Hence to prevent this:
                if [[ ! -e "$rpm_file" ]]; then
                    warn "No RPM driverdisks found in $dd."
                    continue
                fi
                driver-updates --net "$dd" "$rpm_file"
            done
            echo "$dd" >> /tmp/dd_net.done # mark it done so we don't fetch it again
        else
            warn "Failed to fetch drivers from $dd. Processing of directories supported only by NFS."
        fi
    fi
done
