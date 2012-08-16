#/bin/sh
# anaconda-ks-sendheaders.sh - set various HTTP headers for kickstarting

[ -f /tmp/.ks_sendheaders ] && return
command -v set_http_header >/dev/null || . /lib/url-lib.sh

# inst.ks.sendmac: send MAC addresses in HTTP headers
if getargbool 0 kssendmac inst.ks.sendmac; then
    ifnum=0
    for ifname in /sys/class/net/*; do
        [ -e "$ifname/address" ] || continue
        mac=$(cat $ifname/address)
        ifname=${ifname#/sys/class/net/}
        # TODO: might need to choose devices better
        if [ "$ifname" != "lo" ] && [ -n "$mac" ]; then
            # set_http_header is from url-lib.sh, sourced earlier
            set_http_header "X-RHN-Provisioning-MAC-$ifnum" "$ifname $mac"
            ifnum=$(($ifnum+1))
        fi
    done
fi

# inst.ks.sendsn: send system serial number in HTTP headers
if getargbool 0 kssendsn inst.ks.sendsn; then
    system_serial=$(cat /sys/class/dmi/id/product_serial 2>/dev/null)
    if [ -z "$system_serial" ]; then
        warn "inst.ks.sendsn: can't find system serial number"
    else
        set_http_header "X-System-Serial-Number" "$system_serial"
    fi
fi

> /tmp/.ks_sendheaders
