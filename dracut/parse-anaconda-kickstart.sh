#!/bin/bash
# parse-anaconda-kickstart.sh: handle kickstart settings

command -v warn_critical >/dev/null || . /lib/anaconda-lib.sh

# no need to do this twice
[ -f /tmp/ks.cfg.done ] && return

# inst.ks: provide a "URI" for the kickstart file
kickstart="$(getarg inst.ks=)"
if [ -z "$kickstart" ]; then
    getargbool 0 inst.ks && kickstart='nfs:auto'
fi
# no root? the kickstart will probably tell us what our root device is.
[ "$kickstart" ] && [ -z "$root" ] && root="anaconda-kickstart"

# Clear the file for multiple ks urls.
rm -f /tmp/ks_urls

# Is the option for multiple ks urls enabled?
getargbool 0 inst.ks.all && kickstart="urls"

case "${kickstart%%:*}" in
    http|https|ftp|nfs|nfs4) # network kickstart? set "neednet"!
        set_neednet
    ;;
    urls) # multiple network kickstarts?
        locations="$(getargs inst.ks=)"
        get_urls "$locations" >/tmp/ks_urls
        set_neednet
    ;;
    file|path) # "file:<path>" - "path:<path>" is accepted but deprecated
        splitsep ":" "$kickstart" kstype kspath
        if [ -f "$kspath" ]; then
            info "anaconda: parsing kickstart $kspath"
            cp "$kspath" /tmp/ks.cfg
            parse_kickstart /tmp/ks.cfg
            [ "$root" = "anaconda-kickstart" ] && root=""
            true > /tmp/ks.cfg.done
        else
            warn_critical "inst.ks='$kickstart'"
            warn_critical "can't find $kspath!"
        fi
    ;;
esac
export kickstart
