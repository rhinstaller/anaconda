#!/bin/bash
# parse-repo-options.sh: parse the inst.repo= arg and set root/netroot

# If there's a root= arg, we'll just use that
getarg root= >/dev/null && return

repo="$(getarg repo= inst.repo=)"
stage2="$(getarg stage2= inst.stage2=)"

arg="repo"
# default to using repo, but if we have stage2=, use that
[ -n "$stage2" ] && arg="stage2" && repo="$stage2"

# Clean.
rm -f /tmp/stage2_urls

if [ -n "$repo" ]; then
    splitsep ":" "$repo" repotype rest
    case "$repotype" in
        http|https|ftp|nfs|nfs4|nfsiso)
            # Save inst.stage2 urls to the file /tmp/stage2_urls.
            # If all given inst.stage2 locations are urls, we will
            # enable multiple fetching. Otherwise, we will try only
            # the last location, if it is an url.
            locations="$(getargs stage2= inst.stage2=)"

            if are_urls "$locations"; then
                echo "$locations" > /tmp/stage2_urls
            elif are_urls "$stage2"; then
                echo "$stage2" > /tmp/stage2_urls
            fi

            set_neednet; root="anaconda-net:$repo" ;;
        hd|cd|cdrom)
            [ -n "$rest" ] && root="anaconda-disk:$rest" ;;
        hmc)
            # Set arg to copy the complete image to RAM.
            # Otherwise, dracut fails with SquashFS errors.
            echo rd.live.ram=1 >/etc/cmdline.d/99-anaconda-live-ram.conf

            root="anaconda-hmc" ;;
        *)
            warn "Invalid value for 'inst.$arg': $repo" ;;
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
