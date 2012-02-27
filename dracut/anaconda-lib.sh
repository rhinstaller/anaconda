#!/bin/bash

# config_get SECTION KEY < FILE
# read an .ini-style config file, find the KEY in the given SECTION, and return
# the value provided for that key.
# ex: product=$(config_get Main Product < /.buildstamp)
config_get() {
    local section="$1" key="$2" cursec="" k="" v=""
    while read line; do
        case "$line" in
            \#*) continue ;;
            \[*\]*) cursec="${line#[}"; cursec="${cursec%%]*}" ;;
            *=*) k=$(echo ${line%%=*}); v=$(echo ${line#*=}) ;;
        esac
        if [ "$cursec" = "$section" ] && [ "$k" == "$key" ]; then
            echo $v
            break
        fi
    done
}

find_iso() {
    local f="" iso="" isodir="$1" tmpmnt=$(mkuniqdir /run/install tmpmnt)
    for f in $isodir/*.iso; do
        [ -e $f ] || continue
        mount -o loop,ro $f $tmpmnt || continue
        [ -e $tmpmnt/.discinfo ] && iso=$f
        umount $tmpmnt
        if [ "$iso" ]; then echo "$iso"; return 0; fi
    done
    return 1
}

find_runtime() {
    local ti_img="" dir="$1$2"
    ti_img=$(config_get stage2 mainimage < $dir/.treeinfo 2>/dev/null)
    for f in $ti_img images/install.img LiveOS/squashfs.img; do
        [ -e "$dir/$f" ] && echo "$dir/$f"
    done
}

repodir="/run/install/repo"
isodir="/run/install/isodir"
rulesfile="/etc/udev/rules.d/90-anaconda.rules"

anaconda_live_root_dir() {
    local img="" iso="" dir="$1" path="$2"; shift 2
    img=$(find_runtime $repodir$path)
    if [ -n "$img" ]; then
        info "anaconda: found $img"
    else
        iso=$(find_iso $repodir$path)
        [ -n "$iso" ] || { warn "no suitable images"; return 1; }
        info "anaconda: found $iso"
        mount --move $repodir $isodir
        iso=${isodir}${iso#$repodir}
        mount -o loop,ro $iso $repodir
        img=$(find_runtime $repodir) || { warn "$iso has no suitable runtime"; }
    fi
    [ -e "$img" ] && /sbin/dmsquash-live-root $img
}

# These should probably be in dracut-lib or similar

disk_to_dev_path() {
    case "$1" in
        CDLABEL=*|LABEL=*) echo "/dev/disk/by-label/${1#*LABEL=}" ;;
        UUID=*) echo "/dev/disk/by-uuid/${1#UUID=}" ;;
        /dev/*) echo "$1" ;;
        *) echo "/dev/$1" ;;
    esac
}

when_diskdev_appears() {
    local dev="${1#/dev/}" cmd=""; shift
    cmd="/sbin/initqueue --settled --onetime --unique $*"
    {
        printf 'SUBSYSTEM=="block", KERNEL=="%s", RUN+="%s"\n' "$dev" "$cmd"
        printf 'SUBSYSTEM=="block", SYMLINK=="%s", RUN+="%s"\n' "$dev" "$cmd"
    } >> $rulesfile
}

rule_for_netdev() {
    case $1 in
      any)
        printf 'SUBSYSTEM=="net"' ;;
      link)
        printf 'SUBSYSTEM=="net", ATTR{carrier}=="1"' ;;
      ??:??:??:??:??:??)
        printf 'SUBSYSTEM=="net", ATTR{address}=="%s"' "$1" ;;
      *)
        printf 'SUBSYSTEM=="net", ENV{INTERFACE}=="%s"' "$1" ;;
    esac
}

when_netdev_online() {
    local dev="$1" cmd="" rule="" opts='OPTIONS+="event_timeout=360"'; shift
    {
        rule=$(rule_for_netdev $dev)
        cmd='RUN+="/sbin/ifup $env{INTERFACE}"'
        echo "$rule, $opts, $cmd"
        cmd="RUN+=\"/sbin/initqueue --settled --onetime --unique $*\""
        echo "$rule, ACTION==\"online\", $opts, $cmd"
    } >> $rulesfile
}
