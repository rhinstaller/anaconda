#!/bin/bash
# parse-anaconda-dd.sh: handle driver update disk settings

# no need to do this twice
[ -f /tmp/dd_net.done ] && return

command -v getarg >/dev/null || . /lib/dracut-lib.sh

# inst.dd: May provide a "URI" for the driver rpm (possibly more than one)
dd_args="$(getargs dd= inst.dd=)"
for dd in $dd_args; do
    case "${dd%%:*}" in
        http|https|ftp|nfs|nfs4)
            set_neednet
            break
        ;;
    esac
done
