#!/bin/bash
# parse-repo-options.sh: parse the repo= arg (and set root=)

check_depr_arg "method=" "inst.repo=%s"
warn_renamed_arg "repo" "inst.repo"
unset CMDLINE

repo="$(getarg repo= inst.repo=)"

disk_to_dev_path() {
    case "$1" in
        CDLABEL=*|LABEL=*) echo "/dev/disk/by-label/${1#*LABEL=}" ;;
        UUID=*) echo "/dev/disk/by-uuid/${1#UUID=}" ;;
        /dev/*) echo "$1" ;;
        *) echo "/dev/$1" ;;
    esac
}

case "$repo" in
    "") ;; # no repo, no action needed
    cdrom:*)
        root="live:${repo#cdrom:}" ;;
    http:*|https:*|ftp:*)
        treeinfo=$(fetch_url $repo/.treeinfo) && \
          stage2=$(config_get stage2 mainimage < $treeinfo)
        root="live:$repo/${stage2:-images/install.img}" ;;
    nfs:*|nfsiso:*)
        root="anaconda-nfs" # root must be set
        repo=nfs:${repo#nfs*:}
        netroot="anaconda-nfs:$repo"
        wait_for_dev /dev/root ;;
    hd:*)
        splitsep ":" "$repo" f dev path
        root="anaconda.hdiso:$(resolve_disk $dev):$path" ;;
    *)
        warn "Invalid value for 'inst.repo': $repo"
        [ -z "$root" ] && warn "No root= arg either! Will look for media.." ;;
esac

if [ -z "$root" ]; then
    # FIXME: script to watch for valid installer media
    root=live:/dev/sr0
fi

# okay we've got some kind of root thingy to deal with. onward!
rootok=1
