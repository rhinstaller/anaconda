#!/bin/bash

command -v unpack_img >/dev/null || . /lib/img-lib.sh
command -v getarg >/dev/null || . /lib/dracut-lib.sh
command -v fetch_url >/dev/null || . /lib/url-lib.sh

# show critical error messages more visible to user
warn_critical() {
    local msg="$1"
    if ! [ -d /run/anaconda ]; then
        mkdir -p /run/anaconda
    fi
    echo "$msg" >> /run/anaconda/initrd_errors.txt
    warn "$msg"
}

# config_get SECTION KEY < FILE
# read an .ini-style config file, find the KEY in the given SECTION, and return
# the value provided for that key.
# ex: product=$(config_get Main Product < /.buildstamp)
config_get() {
    local section="$1" key="$2" cursec="" k="" v=""
    while read -r line; do
        case "$line" in
            \#*) continue ;;
            \[*\]*) cursec="${line#[}"; cursec="${cursec%%]*}" ;;
            *=*) k="${line%%=*}"; v="${line#*=}" ;;
        esac
        if [ "$cursec" = "$section" ] && [ "$k" == "$key" ]; then
            echo "$v"
            break
        fi
    done
}

find_iso() {
    local f="" p="" iso="" isodir="$1" tmpmnt=""
    tmpmnt=$(mkuniqdir /run/install tmpmnt)
    for f in "$isodir"/*.iso; do
        [ -e "$f" ] || continue
        mount -o loop,ro "$f" "$tmpmnt" || continue
        # Valid ISOs either have stage2 in one of the supported paths
        # or have a .treeinfo that might tell use where to find the stage2 image.
        # If it does not have any of those, it is not valid and will not be used.
        for p in $tmpmnt/LiveOS/squashfs.img $tmpmnt/images/install.img $tmpmnt/.treeinfo; do
            if [ -e "$p" ]; then iso=$f; break; fi
        done
        umount "$tmpmnt"
        if [ "$iso" ]; then echo "$iso"; return 0; fi
    done
    return 1
}

find_runtime() {
    [ -f "$1" ] && [ "${1%.iso}" == "$1" ] && echo "$1" && return
    local ti_img="" dir="$1"
    [ -e "$dir"/.treeinfo ] && \
        ti_img=$(config_get stage2 mainimage < "$dir/.treeinfo")
    for f in $ti_img images/install.img LiveOS/squashfs.img; do
        [ -e "$dir/$f" ] && echo "$dir/$f" && return
    done
}

find_tty() {
    # find the real tty for /dev/console
    local tty="console"
    while [ -f "/sys/class/tty/$tty/active" ]; do
        tty=$(< "/sys/class/tty/$tty/active")
        tty=${tty##* } # last item in the list
    done
    echo "$tty"
}


repodir="/run/install/repo"
isodir="/run/install/isodir"
rulesfile="/etc/udev/rules.d/90-anaconda.rules"

# try to find a usable runtime image from the repo mounted at $mnt.
# if successful, move the mount(s) to $repodir/$isodir.
anaconda_live_root_dir() {
    local img="" iso="" mnt="$1" path="$2"
    img=$(find_runtime "$mnt/$path")
    if [ -n "$img" ]; then
        info "anaconda: found $img"
        [ "$mnt" = "$repodir" ] || { mount --make-rprivate /; mount --move "$mnt" $isodir; }
        anaconda_auto_updates "$repodir/$path/images"
    else
        if [ "${path%.iso}" != "$path" ]; then
            iso=$path
            path=${path%/*.iso}
        else
            iso=$(find_iso "$mnt/$path")
        fi
        [ -n "$iso" ] || { warn "no suitable images"; return 1; }
        info "anaconda: found $iso"
        mount --make-rprivate /
        mount --move "$mnt" $isodir
        iso=${isodir}/${iso#"$mnt"}
        mount -o loop,ro "$iso" $repodir
        img=$(find_runtime $repodir) || { warn "$iso has no suitable runtime"; }
        anaconda_auto_updates $repodir/images
    fi
    anaconda_mount_sysroot "$img"
}

anaconda_net_root() {
    local repo="$1"
    info "anaconda: fetching stage2 from $repo"

    # Try to get the local path to stage2 from treeinfo.
    treeinfo=$(fetch_url "$repo/.treeinfo" 2> /tmp/treeinfo_err) && \
        stage2=$(config_get stage2 mainimage < "$treeinfo")

    # No treeinfo available.
    [ -z "$treeinfo" ] && debug_msg "$(cat /tmp/treeinfo_err)"

    # Use the default local path to stage2.
    if [ -z "$treeinfo" ] || [ -z "$stage2" ]; then
        warn "can't find installer main image path in .treeinfo"
        stage2="images/install.img"
    fi

    # Fetch the stage2.
    if runtime=$(fetch_url "$repo/$stage2") \
        || runtime=$(fetch_url "$repo/LiveOS/squashfs.img"); then

        info "anaconda: successfully fetched stage2 from $repo"

        # NOTE: Should be the same as anaconda_auto_updates()
        updates=$(fetch_url "$repo/images/updates.img" 2> /tmp/updates_err)
        [ -z "$updates" ] && debug_msg "$(cat /tmp/updates_err)"
        [ -n "$updates" ] && unpack_updates_img "$updates" /updates

        product=$(fetch_url "$repo/images/product.img" 2> /tmp/product_err)
        [ -z "$product" ] && debug_msg "$(cat /tmp/product_err)"
        [ -n "$product" ] && unpack_updates_img "$product" /updates

        anaconda_mount_sysroot "$runtime"
        return 0
    fi

    warn_critical "anaconda: failed to fetch stage2 from $repo"
    return 1
}

anaconda_mount_sysroot() {
    local img="$1"
    if [ -e "$img" ]; then
        /sbin/dmsquash-live-root "$img"
        if [ -d /run/rootfsbase ]; then
            # /run/rootfsbase has been created
            # Which means that the Squash filesystem is plain
            # and does not contain the embedded EXT4 inside.
            # Also known as flattened SquashFS or directly compressed SquashFS.
            printf "mount -t overlay LiveOS_rootfs \
                   -o lowerdir=/run/rootfsbase,upperdir=/run/overlayfs,workdir=/run/ovlwork \
                   %s" "${NEWROOT}" > "${hookdir}/mount/01-$$-anaconda.sh"
        else
            # Otherwise, assumption is that /dev/mapper/live-rw should have been created.
            # dracut & systemd only mount things with root=live: so we have to do this ourselves
            # See https://bugzilla.redhat.com/show_bug.cgi?id=1232411
            printf 'mount /dev/mapper/live-rw %s\n' "$NEWROOT" > "$hookdir/mount/01-$$-anaconda.sh"
        fi
    fi
}

# find updates.img/product.img/RHUpdates and unpack/copy them so they'll
# end up in the location(s) that anaconda expects them
anaconda_auto_updates() {
    local dir="$1"
    if [ -d "$dir/RHupdates" ]; then
        copytree "$dir/RHupdates" /updates
    fi
    if [ -e "$dir/updates.img" ]; then
        unpack_updates_img "$dir/updates.img" /updates
    fi
    if [ -e "$dir/product.img" ]; then
        unpack_updates_img "$dir/product.img" /updates
    fi
}

# Unpack an image into the given dir.
unpack_updates_img() {
    local img="$1" tmpdir="/tmp/${1##*/}.$$" outdir="${2:-/updates}"
    # NOTE: unpack_img $img $outdir can clobber existing subdirs in $outdir,
    # which is why we use a tmpdir and copytree (which doesn't clobber)
    unpack_img "$img" "$tmpdir"
    copytree "$tmpdir" "$outdir"
    rm -rf "$tmpdir"
}

# These could probably be in dracut-lib or similar

copytree() {
    local src="$1" dest="$2"
    mkdir -p "$dest"; dest=$(readlink -f -q "$dest")
    ( cd "$src" || return 1; cp -a . -t "$dest" )
}

disk_to_dev_path() {
    case "$1" in
        CDLABEL=*|LABEL=*) echo "/dev/disk/by-label/${1#*LABEL=}" ;;
        UUID=*) echo "/dev/disk/by-uuid/${1#UUID=}" ;;
        /dev/*) echo "$1" ;;
        *) echo "/dev/$1" ;;
    esac
}

find_mount() {
    local dev mnt etc wanted_dev
    wanted_dev="$(readlink -e -q "$1")"
    # shellcheck disable=SC2034  # etc eats the rest of line
    while read -r dev mnt etc; do
        [ "$dev" = "$wanted_dev" ] && echo "$mnt" && return 0
    done < /proc/mounts
    return 1
}

when_diskdev_appears() {
    local dev="${1#/dev/}" cmd=""; shift
    cmd="/sbin/initqueue --settled --onetime --name $1 $*"
    {
        printf 'SUBSYSTEM=="block", KERNEL=="%s", RUN+="%s"\n' "$dev" "$cmd"
        printf 'SUBSYSTEM=="block", SYMLINK=="%s", RUN+="%s"\n' "$dev" "$cmd"
    } >> $rulesfile
}

when_any_cdrom_appears() {
    local cmd="/sbin/initqueue --settled --onetime --name autocd $*"
    printf 'SUBSYSTEM=="block", ENV{ID_CDROM_MEDIA}=="1", RUN+="%s"\n' "$cmd" \
      >> $rulesfile
}

when_any_hmcdrv_appears() {
    local dev="hmcdrv"
    local cmd="/sbin/initqueue --settled --onetime --name $dev $*"
    printf 'KERNEL=="%s", RUN+="%s"\n' "$dev" "$cmd" \
      >> $rulesfile
}

plymouth_running() {
    type plymouth >/dev/null 2>&1 && plymouth --ping 2>/dev/null
}

# print something to the display (and put it in the log so we know what's up)
tell_user() {
    if plymouth_running; then
        # NOTE: if we're doing graphical splash but we don't have all the
        # font-rendering libraries, no message will appear.
        plymouth display-message --text="$*"
        echo "$*"     # this goes to journal only
    else
        echo "$*" >&2 # this goes to journal+console
    fi
}

# print something only in if debug/inst.debug/rd.debug
debug_msg() {
   if getargbool 0 rd.debug || getargbool 0 debug || getargbool 0 inst.debug; then
     echo "$*" >&2
  fi
}

dev_is_cdrom() {
    udevadm info --query=property --name="$1" | grep -q 'ID_CDROM=1'
}

dev_is_on_disk_with_iso9660() {
    # Get the name of the device.
    local dev_name="${1}"

    # Get the path of the device.
    local dev_path
    dev_path="$(udevadm info -q path --name "${dev_name}")"

    # Is the device a partition?
    udevadm info -q property --path "${dev_path}" | grep -q 'DEVTYPE=partition' || return 1

    # Get the path of the parent.
    local disk_path="${dev_path%/*}"

    # Is the parent a disk?
    udevadm info -q property --path "${disk_path}" | grep -q 'DEVTYPE=disk' || return 1

    # Does the parent has the iso9660 filesystem?
    udevadm info -q property --path "${disk_path}" | grep -q 'ID_FS_TYPE=iso9660' || return 1

    return 0
}

# dracut doesn't bring up the network unless:
#   a) $netroot is set (i.e. you have a network root device), or
#   b) /tmp/net.ifaces exists.
# So for non-root things that need the network (like kickstart) we need to
# make sure /tmp/net.ifaces exists.
# For details see 40network/net-genrules.sh (and the rest of 40network).
set_neednet() {
    # if there's no netroot, make sure /tmp/net.ifaces exists
    [ -z "$netroot" ] && true >> /tmp/net.ifaces
}

parse_kickstart() {
    PYTHONHASHSEED=42 /sbin/parse-kickstart "$1" > /etc/cmdline.d/80-kickstart.conf
    unset CMDLINE  # re-read the commandline
    . /tmp/ks.info # save the parsed kickstart
    [ -e "$parsed_kickstart" ] && cp "$parsed_kickstart" /run/install/ks.cfg
}

# print a list of net devices that dracut says are set up.
online_netdevs() {
    local netif=""
    for netif in /tmp/net.*.did-setup; do
        netif=${netif#*.}; netif=${netif%.*}
        [ -d "/sys/class/net/$netif" ] && echo "$netif"
    done
}

# Filter locations that are http, https or ftp urls.
get_urls() {
    local locations="${1}"
    local location

    # Filter locations.
    for location in $locations; do
        case "${location%%:*}" in
            http|https|ftp)
                echo "$location"
            ;;
            *)
                warn "anaconda: this location will be ignored: $location"
            ;;
        esac
    done
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
#
# XXX THIS IS KIND OF A GROSS HACK AND WE NEED A BETTER WAY TO DO IT
run_kickstart() {
    local do_disk="" do_net=""

    # kickstart's done - time to find a real root device
    [ "$root" = "anaconda-kickstart" ] && root=""

    # don't look for the kickstart again
    # shellcheck disable=SC2034  # used by other anaconda-related dracut stuff
    kickstart=""

    # re-parse new cmdline stuff from the kickstart
    . "$hookdir"/cmdline/*parse-anaconda-repo.sh
    . "$hookdir"/cmdline/*parse-livenet.sh
    . "$hookdir"/cmdline/*parse-anaconda-dd.sh

    # Kickstart network configuration (which might even be empty) should be
    # applied to get installer image or driver disks only if the tasks haven't
    # already been performed using network configuration by boot options. This
    # is ensured by the .done files checking.

    case "$root" in
        anaconda-net:*)   [ ! -f /tmp/anaconda_netroot.done ] && do_net=1 ;;
        anaconda-hmc)     do_disk=1 ;;
        anaconda-disk:*)  do_disk=1 ;;
        anaconda-auto-cd) do_disk=1 ;;
    esac
    [ -f /tmp/dd_net ] && [ ! -f /tmp/dd_net.done ] && do_net=1
    [ -f /tmp/dd_disk ] && do_disk=1

    # disk: replay udev events to trigger actions
    if [ "$do_disk" ]; then
        # set up new rules
        . "$hookdir"/pre-trigger/*repo-genrules.sh
        . "$hookdir"/pre-trigger/*driver-updates-genrules.sh
        udevadm control --reload
        # trigger the rules for all the block devices we see
        udevadm trigger --action=change --subsystem-match=block
    fi

    # net: re-run online hooks
    if [ "$do_net" ]; then
        # If NetworkManager is used in initramfs
        if ls -U "$hookdir"/cmdline/*-nm-config.sh >/dev/null 2>&1 ; then
            # First try to re-run online hooks on any online device.
            # We don't want to reconfigure the network by applying kickstart config
            # so use existing network connections if there are any.
            # Based on nm-run.sh
            for _i in /sys/class/net/*/
            do
                state=/run/NetworkManager/devices/$(cat "$_i/ifindex")
                grep -q connection-uuid= "$state" 2>/dev/null || continue
                nm_connected_device_found="yes"
                ifname=$(basename "$_i")
                source_hook initqueue/online "$ifname"
            done

            if [ "${nm_connected_device_found}" != "yes" ]; then
                # Configure NM based on the cmdline now updated with kickstart.
                # The configuration will be applied by the next run of NM
                # via settled hook in *-nm-run.sh script which also calls the
                # online hooks.
                . "$hookdir"/cmdline/*-nm-config.sh
                if [ -n "$DRACUT_SYSTEMD" ]; then
                    systemctl start nm-initrd
                fi
            fi
        else
            # make dracut create the net udev rules (based on the new cmdline)
            . "$hookdir"/pre-udev/*-net-genrules.sh
            udevadm control --reload
            udevadm trigger --action=add --subsystem-match=net
            for netif in $(online_netdevs); do
                source_hook initqueue/online "$netif"
            done
        fi
    fi

    # and that's it - we're back to the mainloop.
    true > /tmp/ks.cfg.done # let wait_for_kickstart know that we're done.
}

wait_for_kickstart() {
    echo "[ -e /tmp/ks.cfg.done ]" > "$hookdir/initqueue/finished/kickstart.sh"
}

wait_for_updates() {
    echo "[ -e /tmp/liveupdates.done ]" > "$hookdir/initqueue/finished/updates.sh"
}

wait_for_dd() {
    echo "[ -e /tmp/dd.done ]" > "$hookdir/initqueue/finished/dd.sh"
}

wait_for_disks() {
    # Allow up to 'inst.wait_for_disks' seconds for disks to be enumerated and
    # related udev rules to execute (defaults to 5 seconds, 0 disables the
    # feature). This prevents dracut-initqueue from finishing early.
    # Since a 0.5 second delay is used between two runs of dracut-initqueue, we
    # force the latter to retry up to twice the value configured, e.g:
    # 'inst.wait_for_disks=15' --> force looping 30 times at least
    # 'inst.wait_for_disks=0'  --> force looping 0 times (so no wait time)
    finished_hook="$hookdir/initqueue/finished/wait_for_disks.sh"
    [ -e "$finished_hook" ] && return
    DISKS_WAIT_DELAY=$(getargnum 5 0 10000 inst.wait_for_disks)
    DISKS_WAIT_RETRIES=$((DISKS_WAIT_DELAY * 2))
    echo "[ \"\$main_loop\" -ge \"$DISKS_WAIT_RETRIES\" ]" > "$finished_hook"
}
