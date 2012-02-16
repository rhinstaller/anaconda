#!/bin/bash
# parse-anaconda-options.sh - parse installer-specific options

. /lib/anaconda-lib.sh
. /lib/url-lib.sh

# THIS! IS! ANACONDA!!!
udevproperty ANACONDA=1
# (used in udev rules to keep stuff like mdadm, multipath, etc. out of our way)

# create the repodir and isodir that anaconda will look for
mkdir -p $repodir $isodir

# get some info from .buildstamp
buildstamp=/run/initramfs/.buildstamp
[ -f /.buildstamp ] && buildstamp=/.buildstamp
if [ ! -f $buildstamp ]; then
    warn ".buildstamp missing"
else
    product=$(config_get Main Product < $buildstamp)
    version=$(config_get Main Version < $buildstamp)
    # TODO: this is silly. There should be an "Arch" item in there..
    uuid=$(config_get Main UUID < $buildstamp)
    strstr "$uuid" "." && arch=${uuid##*.}
fi
[ -z "$arch" ] && arch=$(uname -m)

# set HTTP headers so server(s) will recognize us
set_http_header "X-Anaconda-Architecture" "$arch"
set_http_header "X-Anaconda-System-Release" "$product"

# convenience function to warn the user about old argument names.
warn_renamed_arg() {
    local arg=""
    arg="$(getarg $1)" && warn "'$1=$arg'" && warn "$1 has been renamed to $2"
}

# check for deprecated arg, warn user, and write new arg to /etc/cmdline
check_depr_arg() {
    local arg="" quiet="" newval=""
    if [ "$1" == "--quiet" ]; then quiet=1; shift; fi
    arg="$(getarg $1)"
    [ "$arg" ] || return 1
    newval=$(printf "$2" "$arg")
    [ "$quiet" ] || warn "'$1' is deprecated. Using '$newval' instead."
    echo "$newval" >> /etc/cmdline.d/75anaconda-options.conf
}
check_depr_args() {
    local q=""
    for i in $(getargs $1); do check_depr_arg $q "$i" "$2" && q="--quiet"; done
}

check_depr_arg "serial" "console=ttyS0"
check_depr_arg "stage2=" "root=live:%s"
check_depr_args "blacklist=" "inst.blacklist=%s"
check_depr_arg "nofirewire" "inst.blacklist=firewire_ohci"

# USB is built-in and can't be disabled anymore. DEAL WITH IT.
getarg nousb && warn "'nousb' is deprecated. USB drivers can't be disabled."
getarg ethtool && warn "'ethtool' is deprecated and has been removed."

# interactive junk in initramfs
# (maybe we'll bring it back someday?)
getarg askmethod && warn "'askmethod' is deprecated and has been removed." && \
                    warn "Use an appropriate 'inst.repo=' argument instead."
getarg asknetwork && warn "'asknetwork' is deprecated and has been removed." &&\
                     warn "Use an appropriate 'ip=' argument instead."

check_depr_arg "lang=" "locale.LANG=%s"
check_depr_arg "keymap=" "vconsole.keymap=%s"

# FIXME: if we have ksdevice or multiple ip lines, we'll need interface names
check_depr_arg "dns" "nameserver=%s"
check_depr_arg "ipv6=auto" "ip=auto6"
check_depr_arg "ipv6=dhcp" "ip=dhcp6"
check_depr_arg "ipv6=" "ip=[%s]" # XXX is this right?

check_depr_ip_args() {
    local ip="$(getarg ip=)"
    [ -z "$ip" ] && return       # no ip? no problem
    [ "$ip" = "dhcp" ] && return # this is fine as-is
    strstr "$ip" ":" && return   # PXE/dracut style. this is also fine.

    local nm="$(getarg netmask=)" gw="$(getarg gateway=)" fail=""
    [ -z "$gw" ] && warn "ip=<ip> missing gateway=<gw>!" && fail="yes"
    [ -z "$nm" ] && warn "ip=<ip> missing netmask=<nm>!" && fail="yes"
    [ "$fail" ] && return
    warn "'ip=<ip> gateway=<gw> netmask=<nm>' is deprecated."
    warn "Use 'ip=<ip>::<gw>:<nm>' instead."
    strstr "$gw" ":" && gw="[$gw]" # ipv6 addr (XXX: did anaconda allow this?)
    echo "ip=$ip::$gw:$nm" >> /etc/cmdline.d/75anaconda-options.conf
}
check_depr_ip_args

# re-read the commandline args
unset CMDLINE
