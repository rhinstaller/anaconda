#!/bin/bash
# parse-kickstart-options.sh: check to see if we need to get a kickstart

warn_renamed_arg "ks" "inst.ks"

kickstart="$(getarg ks= inst.ks=)"
if [ -z "$kickstart" ]; then
    getargbool 0 ks inst.ks && kickstart='nfs:auto'
fi

ksdev="$(getarg ksdevice= inst.ks.dev= inst.ks.device=)"

warn_renamed_arg "kssendmac" "inst.ks.sendmac"
if getargbool 0 kssendmac inst.ks.sendmac; then
    ifnum=0
    for ifname in /sys/class/net/*; do
        mac=$(cat $ifname/address)
        ifname=${ifname#/sys/class/net/}
        # TODO: might need to choose devices better
        if [ "$ifname" != "lo" ] && [ -n "$mac" ]; then
            set_http_header "X-RHN-Provisioning-MAC-$ifnum" "$ifname $mac"
            ifnum=$(($ifnum+1))
        fi
    done
fi

warn_renamed_arg "kssendsn" "inst.ks.sendsn"
if getargbool 0 kssendsn inst.ks.sendsn; then
    if ! command -v dmidecode; then
        warn "inst.ks.sendsn: can't find serial number (dmidecode missing)"
    else
        system_serial=$(dmidecode -s system-serial-number)
        set_http_header "X-System-Serial-Number" "$system_serial"
    fi
fi

splitsep ":" "$kickstart" kstype ksdev ksfile
case "$kstype" in
    file|path)
        # It's already here! Parse away!
        if [ "$kstype" = "path" ]; then
            warn "inst.ks='$kickstart'"
            warn "'path:...' is deprecated; please use 'file:...' instead"
        fi
        ksfile=ksdev
        if [ -f "$ksfile" ]; then
            /sbin/parse-kickstart $ksfile >> /etc/cmdline.d/80kickstart.conf
        else
            warn "inst.ks='$kickstart': can't find $ksfile!"
        fi
        ;;
    cdrom|hd)
        # FIXME: mount and parse-kickstart once dev appears
        ;;
    http|https|ftp|nfs|nfs4)
        [ -z "$netroot" ] && netroot="skip"
        # FIXME: schedule fetch-kickstart when network dev comes up
    ;;
    bd) warn "can't get kickstart: biospart isn't supported yet." ;;
esac

# no root? the kickstart will probably tell us what our root device is. Onward!
[ "$kickstart" ] && [ -z "$root" ] && root="kickstart" && rootok=1
