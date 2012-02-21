#!/bin/bash
# parse-repo-options.sh: parse the repo= arg (and set root=)

check_depr_arg "method=" "inst.repo=%s"
warn_renamed_arg "repo" "inst.repo"
unset CMDLINE

repo="$(getarg repo= inst.repo=)"

case "$repo" in
    "") ;; # no repo, no action needed
    cdrom:*)
        root="live:${repo#cdrom:}" ;;
    http:*|https:*|ftp:*)
        root="anaconda-url"
        netroot="anaconda-url:$repo"
        wait_for_dev /dev/root ;;
    nfs:*|nfsiso:*)
        root="anaconda-nfs"
        netroot="anaconda-nfs:${repo#nfs*:}"
        wait_for_dev /dev/root ;;
    hd:*)
        splitsep ":" "$repo" f dev path
        root="anaconda.hdiso:$(disk_to_dev_path $dev):$path" ;;
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
