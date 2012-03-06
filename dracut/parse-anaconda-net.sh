#!/bin/sh
# parse-anaconda-net.sh - parse old deprecated anaconda network setup args

net_conf=/etc/cmdline.d/75-anaconda-network-options.conf

check_depr_arg "dns" "nameserver=%s"

# handle ksdevice (tell us which device to use for ip= stuff later)
ksdev_val=$(getarg ksdevice=)
if [ -n "$ksdev_val" ]; then
    case "$ksdev_val" in
        link)
            warn "'ksdevice=link' does nothing (it's the default behavior)"
        ;;
        ibft)
            warn "'ksdevice=ibft' is deprecated. Using 'ip=ibft' instead."
            echo "ip=ibft" >> $net_conf
            ksdev="ibft0"
        ;;
        bootif)
            warn "'ksdevice=bootif' does nothing (BOOTIF is used by default if present)"
        ;;
        ??:??:??:??:??:??)
            warn "'ksdevice=<MAC>' is deprecated. Using 'ifname=eth0:<MAC>' instead."
            ksdev="eth0"
            echo "ifname=$ksdev:$ksdev_val" >> $net_conf
        ;;
        *) ksdev="$ksdev_val" ;;
    esac
fi
[ -n "$ksdev" ] && echo "ksdevice=$ksdev" >> /tmp/ks.info

ip="$(getarg ip=)"
ipv6="$(getarg ipv6=)"

# XXX NOTE: dracut doesn't do ipv4 + ipv6 (mostly because dhclient doesn't)
if [ -n "$ipv6" ] && [ -n "$ip" ]; then
    warn "'ipv6=$ipv6': can't use ipv6= and ip= simultaneously!"
    warn "defaulting to 'ip=$ip', since 'ipv6=' is deprecated."
    warn "if you need ipv6, use ip=dhcp6|auto6|[v6-address]."
elif [ -n "$ipv6" ]; then # just ipv6
    case "$ipv6" in
        auto) check_depr_arg "ipv6=auto"  "ip=${ksdev:+$ksdev:}auto6" ;;
        dhcp) check_depr_arg "ipv6=dhcp"  "ip=${ksdev:+$ksdev:}dhcp6" ;;
        *)    check_depr_arg "ipv6="      "ip=${ksdev:+$ksdev:}[%s]" ;;
    esac
elif [ -n "$ip" ]; then # just good ol' ipv4
    case "$ip" in
      dhcp|*:*) ;; # these are acceptable for dracut
      *.*.*.*)
          nm="$(getarg netmask=)" || warn "ip=<ip> missing gateway=<gw>!"
          gw="$(getarg gateway=)" || warn "ip=<ip> missing netmask=<nm>!"
          if [ -n "$nm" ] && [ -n "$gw" ]; then
              warn "'ip=<ip> gateway=<gw> netmask=<nm>' is deprecated."
              warn "Use 'ip=<ip>::<gw>:<nm>[:<dev>]' instead."
              strstr "$gw" ":" && gw="[$gw]" # put ipv6 addr in brackets
              echo "ip=$ip::$gw:$nm${ksdev:+:$ksdev}" >> $net_conf
          fi
      ;;
    esac
fi

[ -n "$ip$ipv6$ksdev_val" ] && set_neednet

unset CMDLINE
