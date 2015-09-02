#!/bin/bash
# network root script for anaconda.
# runs in the "online" hook, every time an interface comes online.

command -v getarg >/dev/null || . /lib/dracut-lib.sh
. /lib/anaconda-lib.sh

# initqueue/online hook passes interface name as $1
netif="$1"

# get repo info
splitsep ":" "$root" prefix repo

# repo not set? make sure we are using fresh repo information
if [ -z "$repo" ]; then
     . $hookdir/cmdline/*parse-anaconda-repo.sh
     splitsep ":" "$root" prefix repo
fi

# no repo? non-net root? we're not needed here.
[ "$prefix" = "anaconda-net" ] && [ -n "$repo" ] || return 0
# already done? don't run again.
[ -e /dev/root ] && return 0

# user requested a specific network device, but this isn't it - bail out
[ -n "$ksdevice" ] && [ "$ksdevice" != "$netif" ] && return 0
# user didn't request a specific device, so the first one online wins!
[ -z "$ksdevice" ] && ksdevice="$netif"

command -v config_get >/dev/null || . /lib/anaconda-lib.sh

case $repo in
    nfs*)
        . /lib/nfs-lib.sh
        info "anaconda mounting NFS repo at $repo"
        str_starts "$repo" "nfsiso:" && repo=nfs:${repo#nfsiso:}

        # Replace hex space with a real one. All uses of repo need to be quoted
        # after this point.
        repo=${repo//\\x20/ }

        # Convert nfs4 to nfs:nfsvers=4
        #
        # The reason for this is because anaconda's nfs and dracut's nfs are different.
        # dracut expects options at the end, anaconda puts them after nfs:
        # dracut's nfs_to_var  has a special case to handle anaconda's nfs: form but not nfs4:
        if str_starts "$repo" "nfs4:"; then
            repo=nfs:${repo#nfs4:}
            nfs_to_var "$repo" $netif
            if ! strstr "$options" "vers="; then
                repo="nfs:${options:+$options,}nfsvers=4:$server:$path"
            fi
        else
            # HACK: work around some Mysterious NFS4 Badness (#811242 and friends)
            # by defaulting to nfsvers=3 when no version is requested
            nfs_to_var "$repo" $netif
            if ! strstr "$options" "vers="; then
                repo="nfs:${options:+$options,}nfsvers=3:$server:$path"
            fi
            # END HACK. FIXME: Figure out what is up with nfs4, jeez
        fi
        if [ "${repo%.iso}" == "$repo" ]; then
            mount_nfs "$repo" "$repodir" "$netif" || warn "Couldn't mount $repo"
            anaconda_live_root_dir $repodir
        else
            iso="${repo##*/}"
            mount_nfs "${repo%$iso}" "$repodir" "$netif" || \
                warn "Couldn't mount $repo"
            anaconda_live_root_dir $repodir $iso
        fi
    ;;
    http*|ftp*)
        . /lib/url-lib.sh
        info "anaconda fetching installer from $repo"
        treeinfo=$(fetch_url $repo/.treeinfo 2> /tmp/treeinfo_err) && \
          stage2=$(config_get stage2 mainimage < $treeinfo)
        [ -z "$treeinfo" ] && debug_msg $(cat /tmp/treeinfo_err)
        if [ -z "$treeinfo" -o -z "$stage2" ]; then
            warn "can't find installer mainimage path in .treeinfo"
            stage2="LiveOS/squashfs.img"
        fi
        if runtime=$(fetch_url $repo/$stage2); then
            # NOTE: Should be the same as anaconda_auto_updates()
            updates=$(fetch_url $repo/images/updates.img 2> /tmp/updates_err)
            [ -z "$updates" ] && debug_msg $(cat /tmp/updates_err)
            [ -n "$updates" ] && unpack_updates_img $updates /updates
            product=$(fetch_url $repo/images/product.img 2> /tmp/product_err)
            [ -z "$product" ] && debug_msg $(cat /tmp/product_err)
            [ -n "$product" ] && unpack_updates_img $product /updates
            /sbin/dmsquash-live-root $runtime
        fi
    ;;
    *)
        warn "unknown network repo URL: $repo"
        return 1
    ;;
esac
