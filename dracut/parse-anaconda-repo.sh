#!/bin/bash
# parse-repo-options.sh: parse the inst.repo= arg and set root/netroot

check_depr_arg "method=" "inst.repo=%s"
unset CMDLINE
warn_renamed_arg "repo" "inst.repo"

repo="$(getarg repo= inst.repo=)"
splitsep ":" "$repo" repotype repodev repopath

if [ -n "$repo" ]; then
    case "$repotype" in
        http|https|ftp)
            root="anaconda-url"; netroot="anaconda-url:$repo" ;;
        nfs|nfs4|nfsiso)
            root="anaconda-nfs"; netroot="anaconda-nfs:$repodev:$repopath" ;;
        hd|cd|cdrom)
            root="anaconda-disk:$repodev:$repopath" ;;
        *)
            warn "Invalid value for 'inst.repo': $repo" ;;
    esac
fi

if [ -z "$root" ]; then
    # Alas, no repo arg and no root. Look for valid installer media.
    root="anaconda-auto-cd"
fi

# We've got *some* root variable set.
# Set rootok so we can move on to anaconda-genrules.sh.
rootok=1
