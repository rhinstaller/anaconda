#!/bin/bash
# parse-anaconda-kickstart.sh: handle kickstart settings

# no need to do this twice
[ -f /tmp/ks.cfg.done ] && return

# inst.ks: provide a "URI" for the kickstart file
kickstart="$(getarg ks= inst.ks=)"
if [ -z "$kickstart" ]; then
    getargbool 0 ks inst.ks && kickstart='nfs:auto'
fi
# no root? the kickstart will probably tell us what our root device is.
[ "$kickstart" ] && [ -z "$root" ] && root="anaconda-kickstart"

# Clean.
rm -f /tmp/ks_urls

case "${kickstart%%:*}" in
    http|https|ftp|nfs|nfs4) # network kickstart? set "neednet"!
        # Save inst.ks urls to the file /tmp/ks_urls.
        # If all given inst.ks locations are urls, we will
        # enable multiple fetching. Otherwise, we will try
        # only the last location, if it is an url.
        locations="$(getargs ks= inst.ks=)"

        if are_urls "$locations"; then
            echo "$locations" > /tmp/ks_urls
        elif are_urls "$kickstart"; then
            echo "$kickstart" > /tmp/ks_urls
        fi

        set_neednet
    ;;
    file|path) # "file:<path>" - "path:<path>" is accepted but deprecated
        splitsep ":" "$kickstart" kstype kspath
        if [ -f "$kspath" ]; then
            info "anaconda: parsing kickstart $kspath"
            cp $kspath /tmp/ks.cfg
            parse_kickstart /tmp/ks.cfg
            [ "$root" = "anaconda-kickstart" ] && root=""
            > /tmp/ks.cfg.done
        else
            warn "inst.ks='$kickstart'"
            warn "can't find $kspath!"
        fi
    ;;
esac
export kickstart
