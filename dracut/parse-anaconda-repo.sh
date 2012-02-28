#!/bin/bash
# parse-repo-options.sh: parse the inst.repo= arg and set root/netroot

repo="$(getarg repo= inst.repo=)"

if [ -n "$repo" ]; then
    splitsep ":" "$repo" repotype rest
    case "$repotype" in
        http|https|ftp)
            root="anaconda-url"; netroot="anaconda-url:$repo" ;;
        nfs|nfs4|nfsiso)
            root="anaconda-nfs"; netroot="anaconda-nfs:$rest" ;;
        hd|cd|cdrom)
            [ -n "$rest" ] && root="anaconda-disk:$rest" ;;
        *)
            warn "Invalid value for 'inst.repo': $repo" ;;
    esac
fi

if [ -z "$root" ]; then
    # No repo arg, no kickstart, and no root. Search for valid installer media.
    root="anaconda-auto-cd"
fi

# We've got *some* root variable set.
# Set rootok so we can move on to anaconda-genrules.sh.
rootok=1
