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

check_isodir() {
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

mount_isodir() {
    local mnt="$1" path="$2" dir="$1$2"
    iso=$(check_isodir $dir)
    [ "$iso" ] || return
    local isodir=$(mkuniqdir /run/install isodir)
    mount --move $mnt $isodir
    iso=${isodir}${iso#$mnt}
    mount -o loop,ro $iso $mnt
    img=$(find_runtime $mnt)
    if [ -z "$img" ]; then
        umount $mnt
        rmdir $isodir
        return 1
    else
        echo $img
    fi
}
