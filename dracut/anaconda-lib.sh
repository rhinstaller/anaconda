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

# These could probably be in dracut-lib or similar

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

set_neednet() {
    if ! getargbool 0 rd.neednet; then
        echo "rd.neednet=1" >> /etc/cmdline.d/anaconda-neednet.conf
    fi
    unset CMDLINE
}

when_netdev_online() {
    printf 'SUBSYSTEM=="net", ACTION=="online", RUN+="%s"\n' \
             "/sbin/initqueue --settled $@" >> $rulesfile
}

# Kickstart parsing goes at the end 'cuz it might use the other stuff

parse_kickstart() {
    /sbin/parse-kickstart $1 > /etc/cmdline.d/80kickstart.conf
    if [ -e /tmp/ks.info ]; then
        . /tmp/ks.info
        cp $parsed_kickstart /run/install/ks.cfg
    fi
}

# This is where we actually run the kickstart. Whee!
# We can't just add udev rules (we'll miss devices that are already active),
# and we can't just run the scripts manually (we'll miss devices that aren't
# yet active - think driver disks!).
#
# So: we have to write out the rules and then retrigger them.
#
# Really what we want to do here is just start over from the "cmdline"
# phase, but since we can't do that, we'll kind of fake it.
run_kickstart() {
    local triggers="" do_repo=0 # TODO: do_dd, do_updates, any others?

    # figure out what to re-run
    grep -q 'inst\.repo=' /etc/cmdline.d/80kickstart.conf && do_repo=1

    # parse cmdline
    [ $do_repo ] && . $hookdir/cmdline/*parse-anaconda-repo.sh

    # write udev rules
    [ $do_repo ] && . $hookdir/pre-udev/*repo-genrules.sh

    # figure out if we need to replay udev events
    if [ $do_repo ]; then
        # update root.info for ifup/netroot
        { echo "root='$root'"; echo "netroot='$netroot'"; } >> /tmp/root.info
        case "$repotype" in
            http|https|ftp) triggers="$triggers --subsystem-match=net" ;;
            cdrom|hd|bd)    triggers="$triggers --subsystem-match=block" ;;
        esac
    fi

    # load and trigger new rules, if needed
    if [ -n "$triggers" ]; then
        udevadm control --reload
        udevadm trigger $triggers
    fi

    # and that's it - we're back to the mainloop.
    > /tmp/ks.cfg.done # let wait_for_kickstart know that we're done.
}

wait_for_kickstart() {
    echo "[ -e /tmp/ks.cfg.done ]" > $hookdir/initqueue/finished/kickstart.sh
}
