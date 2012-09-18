#!/bin/bash
# module-setup.sh for anaconda

check() {
    [[ $hostonly ]] && return 1
    return 255 # this module is optional
}

depends() {
    echo livenet nfs img-lib convertfs ifcfg
    case "$(uname -m)" in
        s390*) echo cms ;;
    esac
    return 0
}

install() {
    # anaconda
    inst "$moddir/anaconda-lib.sh" "/lib/anaconda-lib.sh"
    inst_hook cmdline 25 "$moddir/parse-anaconda-options.sh"
    inst_hook cmdline 26 "$moddir/parse-anaconda-kickstart.sh"
    inst_hook cmdline 27 "$moddir/parse-anaconda-repo.sh"
    inst_hook cmdline 28 "$moddir/parse-anaconda-net.sh"
    inst_hook pre-udev 30 "$moddir/anaconda-modprobe.sh"
    inst_hook pre-udev 40 "$moddir/repo-genrules.sh"
    inst_hook pre-udev 40 "$moddir/kickstart-genrules.sh"
    inst_hook pre-udev 40 "$moddir/updates-genrules.sh"
    inst_hook pre-trigger 40 "$moddir/anaconda-udevprop.sh"
    inst_hook initqueue/settled 00 "$moddir/anaconda-ks-sendheaders.sh"
    inst_hook initqueue/online 80 "$moddir/anaconda-netroot.sh"
    inst "$moddir/anaconda-diskroot" "/sbin/anaconda-diskroot"
    inst_hook pre-pivot 99 "$moddir/anaconda-copy-ks.sh"
    inst_hook pre-pivot 99 "$moddir/anaconda-copy-cmdline.sh"
    # kickstart parsing, WOOOO
    inst_hook initqueue/online 10 "$moddir/fetch-kickstart-net.sh"
    inst "$moddir/fetch-kickstart-disk" "/sbin/fetch-kickstart-disk"
    inst "$moddir/fetch-updates-disk" "/sbin/fetch-updates-disk"
    inst "$moddir/parse-kickstart" "/sbin/parse-kickstart"
    # python deps for parse-kickstart. DOUBLE WOOOO
    $moddir/python-deps $moddir/parse-kickstart | while read dep; do
        case "$dep" in
            *.so) inst_library $dep ;;
            *.py) inst_simple $dep ;;
            *) inst $dep ;;
        esac
    done
}

