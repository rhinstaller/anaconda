#!/bin/sh
# parse-anaconda-net.sh - parse old deprecated anaconda network setup args

net_conf=/etc/cmdline.d/75-anaconda-network-options.conf

check_depr_arg "dns" "nameserver=%s"

# handle ksdevice (tell us which device to use for ip= stuff later)
export ksdevice=""
ksdev_val=$(getarg ksdevice=)
if [ -n "$ksdev_val" ]; then
    case "$ksdev_val" in
        link)
            warn "'ksdevice=link' does nothing (it's the default behavior)"
        ;;
        ibft)
            warn "'ksdevice=ibft' is deprecated. Using 'ip=ibft' instead."
            echo "ip=ibft" > $net_conf
            ksdevice="ibft0"
        ;;
        bootif)
            warn "'ksdevice=bootif' does nothing (BOOTIF is used by default if present)"
        ;;
        ??:??:??:??:??:??)
            warn "'ksdevice=<MAC>' is deprecated. Using 'ifname=ksdev0:<MAC>' instead."
            ksdevice="ksdev0"
            echo "ifname=$ksdevice:$ksdev_val" > $net_conf
        ;;
        *) ksdevice="$ksdev_val" ;;
    esac
fi
[ -n "$ksdevice" ] && echo "bootdev=$ksdevice" >> $net_conf

ip="$(getarg ip=)"
ipv6="$(getarg ipv6=)"

# XXX NOTE: dracut doesn't do ipv4 + ipv6 (mostly because dhclient doesn't)
if [ -n "$ipv6" ] && [ -n "$ip" ]; then
    warn "'ipv6=$ipv6': can't use ipv6= and ip= simultaneously!"
    warn "defaulting to 'ip=$ip', since 'ipv6=' is deprecated."
    warn "if you need ipv6, use ip=dhcp6|auto6|[v6-address]."
elif [ -n "$ipv6" ]; then # just ipv6
    case "$ipv6" in
        auto) check_depr_arg "ipv6=auto"  "ip=${ksdevice:+$ksdevice:}auto6" ;;
        dhcp) check_depr_arg "ipv6=dhcp"  "ip=${ksdevice:+$ksdevice:}dhcp6" ;;
        *)    check_depr_arg "ipv6="      "ip=${ksdevice:+$ksdevice:}[%s]" ;;
    esac
fi

[ -n "$ip$ipv6$ksdev_val" ] && set_neednet

# set dhcp vendor class
dhcpclass=$(getarg inst.dhcpclass) || dhcpclass="anaconda-$(uname -srm)"
echo "send vendor-class-identifier \"$dhcpclass\";" >> /etc/dhclient.conf

unset CMDLINE
