#!/bin/bash
# parse-repo-options.sh: parse the inst.repo= arg and set root/netroot

# If there's a root= arg, we'll just use that
getarg root= >/dev/null && return

repo="$(getarg repo= inst.repo=)"
stage2="$(getarg stage2= inst.stage2=)"

arg="repo"
# default to using repo, but if we have stage2=, use that
[ -n "$stage2" ] && arg="stage2" && repo="$stage2"

# Clear the file for multiple stage2 urls.
rm -f /tmp/stage2_urls

# Is the option for multiple stage2 urls enabled?
getargbool 0 inst.stage2.all && repo="urls"

if [ -n "$repo" ]; then
    splitsep ":" "$repo" repotype rest
    case "$repotype" in
        http|https|ftp|nfs|nfs4|nfsiso)
            root="anaconda-net:$repo"
            set_neednet
        ;;
        urls)
            root="anaconda-net:urls"
            locations="$(getargs stage2= inst.stage2=)"
            get_urls "$locations" >/tmp/stage2_urls
            set_neednet
        ;;
        hd|cd|cdrom)
            [ -n "$rest" ] && root="anaconda-disk:$rest"
        ;;
        hmc)
            # Set arg to copy the complete image to RAM.
            # Otherwise, dracut fails with SquashFS errors.
            echo rd.live.ram=1 >/etc/cmdline.d/99-anaconda-live-ram.conf

            root="anaconda-hmc"
        ;;
        *)
            warn "Invalid value for 'inst.$arg': $repo"
        ;;
    esac
fi

if [ -z "$root" ]; then
    # No repo arg, no kickstart, and no root. Search for valid installer media.
    root="anaconda-auto-cd"
fi

# Make sure we wait for the dmsquash root device to appear
case "$root" in
    anaconda-*) wait_for_dev /dev/root ;;
esac

# We've got *some* root variable set.
# Set rootok so we can move on to anaconda-genrules.sh.
rootok=1
