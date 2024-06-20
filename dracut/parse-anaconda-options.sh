#!/bin/bash
# parse-anaconda-options.sh - parse installer-specific options

. /lib/anaconda-lib.sh
. /lib/url-lib.sh

# create the repodir and isodir that anaconda will look for
mkdir -p "$repodir" "$isodir"

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
echo Loading "$product" "$version" "$arch" installer...

# set HTTP headers so server(s) will recognize us
set_http_header "X-Anaconda-Architecture" "$arch"
set_http_header "X-Anaconda-System-Release" "$product"

# convenience function to warn the user about old argument names.
warn_renamed_arg() {
    local arg=""
    arg="$(getarg "$1")" && warn_critical "'$1=$arg'" && \
        warn_critical "$1 has been deprecated and will be removed. Please use $2 instead."
}

# check for deprecated arg, warn user, and write new arg to /etc/cmdline
check_depr_arg() {
    local arg="" quiet="" newval=""
    if [ "$1" == "--quiet" ]; then quiet=1; shift; fi
    arg="$(getarg "$1")"
    [ "$arg" ] || return 1
    # shellcheck disable=SC2059  # yes, $2 *is* the format string
    newval=$(printf "$2" "$arg")
    [ "$quiet" ] || warn_critical "'$1' is deprecated. Using '$newval' instead."
    echo "$newval" >> /etc/cmdline.d/75-anaconda-options.conf
}
check_depr_args() {
    local q=""
    for i in $(getargs "$1"); do check_depr_arg "$q" "$i" "$2" && q="--quiet"; done
}
check_removed_arg() {
    local arg="$1"; shift
    if getarg "$arg" > /dev/null; then
        warn_critical "'$arg' is deprecated and has been removed."
        [ -n "$*" ] && warn_critical "$*"
    fi
}

check_removed_no_inst_arg() {
    local removed_arg="$1" new_arg="$2"
    check_removed_arg "$removed_arg" "All usage of Anaconda boot arguments without 'inst.' prefix \
was removed. Please use $new_arg instead."
}

# ssh
check_removed_no_inst_arg "sshd" "inst.sshd"

# serial was never supposed to be used for anything!
check_removed_arg serial "To change the console use 'console=' instead."
# USB is built-in and can't be disabled anymore. DEAL WITH IT.
check_removed_arg nousb "USB drivers can't be disabled."
# ethtool is gone. Who forces their devices to single-duplex anymore?
check_removed_arg ethtool

# interactive junk in initramfs
# (maybe we'll bring it back someday?)
check_removed_arg askmethod "Use an appropriate 'inst.repo=' argument instead."
check_removed_arg asknetwork "Use an appropriate 'ip=' argument instead."

# lang & keymap
check_removed_no_inst_arg "lang" "inst.lang"
check_removed_no_inst_arg "keymap" "inst.keymap"

# repo
check_depr_arg "method=" "repo=%s"
check_removed_no_inst_arg "repo" "inst.repo"

# stage2
check_removed_no_inst_arg "stage2" "inst.stage2"

# kickstart
check_removed_no_inst_arg "ks" "inst.ks"
check_removed_no_inst_arg "kssendmac" "inst.ks.sendmac"
check_removed_no_inst_arg "kssendsn" "inst.ks.sendsn"

# mpath
check_removed_arg "inst.nompath"

# dmraid & nodmraid
check_removed_arg "inst.dmraid"
check_removed_arg "inst.nodmraid"

# Ignore self-signed SSL certs
check_removed_no_inst_arg "noverifyssl" "inst.noverifyssl"
if getargbool 0 inst.noverifyssl; then
    # Tell dracut to use curl --insecure
    echo "rd.noverifyssl" >> /etc/cmdline.d/75-anaconda-options.conf
fi

# add proxy= to the dracut so stage1 downloads (stage2,kickstart...) don't ignore inst.proxy
if proxy=$(getarg inst.proxy); then
    echo "proxy=$proxy" >> /etc/cmdline.d/75-anaconda-options.conf
fi

# updates
check_removed_no_inst_arg "updates" "inst.updates"
if updates=$(getarg inst.updates); then
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

# for rdp bring network up in initramfs so that cmdline configuration is used
check_removed_no_inst_arg "rdp" "inst.rdp"
getargbool 0 inst.rdp && warn "anaconda requiring network for RDP" && set_neednet

# Driver Update Disk
check_removed_no_inst_arg "dd" "inst.dd"

# re-read the commandline args
unset CMDLINE
