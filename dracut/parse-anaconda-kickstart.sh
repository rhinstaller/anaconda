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

case "${kickstart%%:*}" in
    http|https|ftp|nfs|nfs4) # network kickstart? set "neednet"!
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
