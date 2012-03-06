#!/bin/bash
# network root script for anaconda.
# runs in the "online" hook, every time an interface comes online.

command -v getarg >/dev/null || . /lib/dracut-lib.sh

# get repo and root info
[ -e /tmp/root.info ] && . /tmp/root.info
repo=$(getarg repo= inst.repo=)

# no repo? non-net root? we're not needed here.
[ "$root" = "anaconda-net" ] && [ -n "$repo" ] || return 0

# get network/kickstart info
[ -e /tmp/ks.info ] && . /tmp/ks.info
# user requested a specific network device, but this isn't it - bail out
[ -n "$ksdevice" ] && [ "$ksdevice" != "$netif" ] && return 0

command -v config_get >/dev/null || . /lib/anaconda-lib.sh

case $repo in
    nfs*)
        . /lib/nfs-lib.sh
        info "anaconda mounting NFS repo at $repo"
        mount_nfs "$repo" "$repodir" "$netif" || warn "Couldn't mount $repo"
        anaconda_live_root_dir $repodir
    ;;
    http*|ftp*)
        . /lib/url-lib.sh
        info "anaconda fetching installer from $repo"
        treeinfo=$(fetch_url $repo/.treeinfo) && \
          stage2=$(config_get stage2 mainimage < $treeinfo)
        if [ -z "$stage2" ]; then
            warn "can't find installer mainimage path in .treeinfo"
            stage2="LiveOS/squashfs.img"
        fi
        runtime=$(fetch_url $repo/$stage2) && /sbin/dmsquash-live-root $runtime
    ;;
    *)
        warn "unknown network repo URL: $repo"
    ;;
esac
