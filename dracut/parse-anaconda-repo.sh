#!/bin/bash
# parse-repo-options.sh: parse the inst.repo= arg and set root/netroot

check_depr_arg "method=" "inst.repo=%s"
warn_renamed_arg "repo" "inst.repo"
unset CMDLINE

repo="$(getarg repo= inst.repo=)"
splitsep ":" "$repo" f repodev repopath

if [ -n "$repo" ]; then
    case "$repo" in
        http:*|https:*|ftp:*)
            root="anaconda-url"; netroot="anaconda-url:$repo" ;;
        nfs:*|nfsiso:*)
            root="anaconda-nfs"; netroot="anaconda-nfs:${repo#nfs*:}" ;;
        hd:*)
            root="anaconda-hd:$(disk_to_dev_path $repodev):$path" ;;
        cdrom:*)
            root="anaconda-cd:$(disk_to_dev_path $repodev)" ;;
        *)
            warn "Invalid value for 'inst.repo': $repo" ;;
    esac
fi

if [ -z "$root" ]; then
    # Alas, no repo/method arg and no root. Look for valid installer media.
    #root="anaconda-auto-cd" # TODO: use this once we have the autoprober
    root=live:/dev/sr0       # XXX laaaame temp workaround
fi

# We've got *some* root variable set.
# Set rootok so we can move on to anaconda-genrules.sh.
rootok=1
