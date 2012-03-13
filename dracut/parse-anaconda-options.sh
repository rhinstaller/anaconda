#!/bin/bash
# parse-anaconda-options.sh - parse installer-specific options

. /lib/anaconda-lib.sh
. /lib/url-lib.sh

# create the repodir and isodir that anaconda will look for
mkdir -p $repodir $isodir

# add some modules
modprobe -q edd

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
# ethtool is gone. Who forces their devices to single-duplex anymore?
getarg ethtool && warn "'ethtool' is deprecated and has been removed."

# interactive junk in initramfs
# (maybe we'll bring it back someday?)
getarg askmethod && warn "'askmethod' is deprecated and has been removed." && \
                    warn "Use an appropriate 'inst.repo=' argument instead."
getarg asknetwork && warn "'asknetwork' is deprecated and has been removed." &&\
                     warn "Use an appropriate 'ip=' argument instead."

# lang & keymap
check_depr_arg "lang=" "locale.LANG=%s"
check_depr_arg "keymap=" "vconsole.keymap=%s"

# repo
check_depr_arg "method=" "inst.repo=%s"
warn_renamed_arg "repo" "inst.repo"

# kickstart
warn_renamed_arg "ks" "inst.ks"
warn_renamed_arg "ksdevice" "inst.ks.device"
warn_renamed_arg "kssendmac" "inst.ks.sendmac"
warn_renamed_arg "kssendsn" "inst.ks.sendsn"

# re-read the commandline args
unset CMDLINE
