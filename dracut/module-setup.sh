#!/bin/bash
# module-setup.sh for anaconda

check() {
    [[ $hostonly ]] && return 1
    return 255 # this module is optional
}

depends() {
    echo livenet nfs img-lib convertfs
    return 0
}

install() {
    # anaconda
    inst "$moddir/anaconda-lib.sh" "/lib/anaconda-lib.sh"
    inst_hook cmdline 25 "$moddir/parse-anaconda-options.sh"
    inst_hook cmdline 26 "$moddir/parse-anaconda-kickstart.sh"
    inst_hook cmdline 27 "$moddir/parse-anaconda-repo.sh"
    inst_hook pre-udev 40 "$moddir/repo-genrules.sh"
    inst "$moddir/anaconda-nfsroot" "/sbin/anaconda-nfsroot"
    inst "$moddir/anaconda-hdroot" "/sbin/anaconda-hdroot"
    inst_hook pre-pivot 99 "$moddir/anaconda-copy-ks.sh"
    # binaries we need sometimes
    dracut_install -o dmidecode
    # kickstart parsing, WOOOO
    inst "$moddir/fetch-kickstart" "/sbin/fetch-kickstart"
    inst "$moddir/parse-kickstart" "/sbin/parse-kickstart"
    # python deps for parse-kickstart. DOUBLE WOOOO
    $moddir/pythondeps.sh $moddir/parse-kickstart | while read dep; do
        case "$dep" in
            *.so) inst_library $dep ;;
            *.py) inst_simple $dep ;;
            *) inst $dep ;;
        esac
    done
}

