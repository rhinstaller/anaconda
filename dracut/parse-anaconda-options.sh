#!/bin/bash
# parse-anaconda-options.sh - parse installer-specific options

. /lib/anaconda-lib.sh
. /lib/url-lib.sh

# create the repodir and isodir that anaconda will look for
mkdir -p $repodir $isodir

# add some modules
modprobe -q edd

# NOTE: anaconda historically activated all the fancy disk devices itself,
# and it would get very confused if they were already active when it started.
# F17 has some support for handling already-active devices, but it's still
# currently safer to disable these things and let anaconda activate them.
# TODO FIXME: remove this and make anaconda handle active devices!
{
    for t in dm md lvm luks; do
        # disable unless specifically enabled
        getargbool 0 rd.$t || echo rd.$t=0
    done
} > /etc/cmdline.d/99-anaconda-disable-disk-activation.conf

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
echo Loading $product $version $arch installer...

# set HTTP headers so server(s) will recognize us
set_http_header "X-Anaconda-Architecture" "$arch"
set_http_header "X-Anaconda-System-Release" "$product"

# convenience function to warn the user about old argument names.
warn_renamed_arg() {
    local arg=""
    arg="$(getarg $1)" && warn "'$1=$arg'" && warn "$1 has been renamed to $2"
}

warn_renamed_arg() { :; } # XXX REMOVE WHEN WE'RE READY FOR THE NEW NAMES.

# check for deprecated arg, warn user, and write new arg to /etc/cmdline
check_depr_arg() {
    local arg="" quiet="" newval=""
    if [ "$1" == "--quiet" ]; then quiet=1; shift; fi
    arg="$(getarg $1)"
    [ "$arg" ] || return 1
    newval=$(printf "$2" "$arg")
    [ "$quiet" ] || warn "'$1' is deprecated. Using '$newval' instead."
    echo "$newval" >> /etc/cmdline.d/75-anaconda-options.conf
}
check_depr_args() {
    local q=""
    for i in $(getargs $1); do check_depr_arg $q "$i" "$2" && q="--quiet"; done
}
check_removed_arg() {
    local arg="$1"; shift
    if getarg "$arg" > /dev/null; then
        warn "'$arg' is deprecated and has been removed."
        [ -n "$*" ] && warn "$*"
    fi
}

check_depr_args "blacklist=" "inst.blacklist=%s"
check_depr_arg "nofirewire" "inst.blacklist=firewire_ohci"

# ssh
check_depr_arg "sshd" "inst.sshd"

# serial was never supposed to be used for anything!
check_removed_arg serial "To change the console use 'console=' instead."
# USB is built-in and can't be disabled anymore. DEAL WITH IT.
check_removed_arg nousb "USB drivers can't be disabled."
# ethtool is gone. Who forces their devices to single-duplex anymore?
check_removed_arg ethtool

# interactive junk in initramfs
# (maybe we'll bring it back someday?)
check_removed_arg asknetwork "Use an appropriate 'ip=' argument instead."

# lang & keymap
warn_renamed_arg "lang" "inst.lang"
warn_renamed_arg "keymap" "inst.keymap"

# repo
check_depr_arg "method=" "repo=%s"
warn_renamed_arg "repo" "inst.repo"

# kickstart
warn_renamed_arg "ks" "inst.ks"
warn_renamed_arg "ksdevice" "inst.ks.device"
warn_renamed_arg "kssendmac" "inst.ks.sendmac"
warn_renamed_arg "kssendsn" "inst.ks.sendsn"

# Ignore self-signed SSL certs
warn_renamed_arg "noverifyssl" "inst.noverifyssl"
if $(getargbool 0 noverifyssl inst.noverifyssl); then
    # Tell dracut to use curl --insecure
    echo "rd.noverifyssl" >> /etc/cmdline.d/75-anaconda-options.conf
fi

# updates
warn_renamed_arg "updates=" "inst.updates"
if updates=$(getarg updates inst.updates); then
    if [ -n "$updates" ]; then
        export anac_updates=$updates
        case $updates in
            http*|ftp*|nfs*)
                echo "live.updates=$updates" \
                  >> /etc/cmdline.d/75-anaconda-options.conf ;;
        esac
    else
        warn "'updates' requires a location for the updates disk"
    fi
fi

# for vnc bring network up in initramfs so that cmdline configuration is used
getargbool 0 vnc inst.vnc && warn "anaconda requiring network for vnc" && set_neednet

# Driver Update Disk
warn_renamed_arg "dd" "inst.dd"

# re-read the commandline args
unset CMDLINE
