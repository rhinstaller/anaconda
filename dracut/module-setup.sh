#!/bin/bash
# module-setup.sh for anaconda
set -eu -o pipefail

check() {
    if [[ $hostonly ]]; then
        derror "The anaconda module doesn't support the host-only mode."
        return 1
    fi
    return 255 # this module is optional
}

depends() {
    echo livenet nfs img-lib convertfs net-lib
    case "$(uname -m)" in
        s390*) echo cms ;;
    esac
    return 0
}

installkernel() {
    case "$(uname -m)" in
        s390*) instmods hmcdrv ;;
    esac
}

install() {
    # binaries for easier debugging (requested by https://issues.redhat.com/browse/RHEL-5719)
    dracut_install ping
    # binaries we want in initramfs
    dracut_install eject -o pigz
    dracut_install depmod blkid
    # Deps for fetch-kickstart-disk
    dracut_install mount umount cp mkdir rmdir
    inst_binary /usr/libexec/anaconda/dd_list /bin/dd_list
    inst_binary /usr/libexec/anaconda/dd_extract /bin/dd_extract

    # anaconda
    inst "$moddir/anaconda-lib.sh" "/lib/anaconda-lib.sh"
    inst_hook cmdline 25 "$moddir/parse-anaconda-options.sh"
    inst_hook cmdline 26 "$moddir/parse-anaconda-kickstart.sh"
    inst_hook cmdline 27 "$moddir/parse-anaconda-repo.sh"
    inst_hook cmdline 28 "$moddir/parse-anaconda-net.sh"
    inst_hook cmdline 99 "$moddir/anaconda-start-dnsconfd.sh"
    inst_hook pre-udev 30 "$moddir/anaconda-modprobe.sh"
    inst_hook pre-trigger 50 "$moddir/repo-genrules.sh"
    inst_hook pre-trigger 50 "$moddir/kickstart-genrules.sh"
    inst_hook pre-trigger 50 "$moddir/updates-genrules.sh"
    inst_hook initqueue/settled 00 "$moddir/anaconda-ks-sendheaders.sh"
    inst_hook initqueue/online 00 "$moddir/anaconda-ifcfg.sh"
    inst_hook initqueue/online 80 "$moddir/anaconda-netroot.sh"
    inst "$moddir/anaconda-diskroot" "/sbin/anaconda-diskroot"
    inst_hook pre-pivot 50 "$moddir/anaconda-copy-ks.sh"
    inst_hook pre-pivot 50 "$moddir/anaconda-copy-cmdline.sh"
    inst_hook pre-pivot 90 "$moddir/anaconda-copy-dhclient.sh"
    inst_hook pre-pivot 91 "$moddir/anaconda-copy-prefixdevname.sh"
    inst_hook pre-pivot 92 "$moddir/anaconda-dnsconfd.sh"
    inst_hook pre-pivot 92 "$moddir/anaconda-copy-certs.sh"
    inst_hook pre-pivot 95 "$moddir/anaconda-set-kernel-hung-timeout.sh"
    inst_hook pre-pivot 99 "$moddir/save-initramfs.sh"
    inst_hook cleanup 98 "$moddir/anaconda-nfsrepo-cleanup.sh"
    inst_hook pre-shutdown 50 "$moddir/anaconda-pre-shutdown.sh"
    # kickstart parsing, WOOOO
    inst_hook initqueue/online 11 "$moddir/fetch-kickstart-net.sh"
    inst "$moddir/fetch-kickstart-disk" "/sbin/fetch-kickstart-disk"
    inst "$moddir/fetch-updates-disk" "/sbin/fetch-updates-disk"
    inst "$moddir/parse-kickstart" "/sbin/parse-kickstart"
    # this is imported by parse-kickstart and is easiest to just dump into the same directory
    inst "$moddir/kickstart_version.py" "/sbin/kickstart_version.py"
    # Driver Update Disks
    inst_hook cmdline 29 "$moddir/parse-anaconda-dd.sh"
    inst_hook pre-trigger 55 "$moddir/driver-updates-genrules.sh"
    inst_hook initqueue/online 20 "$moddir/fetch-driver-net.sh"
    inst_hook pre-pivot 50 "$moddir/anaconda-depmod.sh"
    inst "$moddir/find-net-intfs-by-driver" "/bin/find-net-intfs-by-driver"
    inst "$moddir/anaconda-ifdown" "/bin/anaconda-ifdown"
    inst "$moddir/driver_updates.py" "/bin/driver-updates"
    inst "/usr/sbin/modinfo"
    inst_simple "$moddir/driver-updates@.service" "/etc/systemd/system/driver-updates@.service"
    # Make the /usr mountpoint RW in Dracut with systemd version >= 256, see RHEL-77192 for details.
    inst_simple "$moddir/20_rw_usr.conf" "/etc/systemd/system.conf.d/20_rw_usr.conf"
    # rpm configuration file (needed by dd_extract)
    inst "/usr/lib/rpm/rpmrc"
    # timeout script for errors reporting
    inst_hook initqueue/timeout 50 "$moddir/anaconda-error-reporting.sh"
    # python deps for parse-kickstart. DOUBLE WOOOO
    PYTHONHASHSEED=42 "$moddir/python-deps" "$moddir/parse-kickstart" "$moddir/driver_updates.py" | while read -r dep; do
        case "$dep" in
            *.so) inst_library "$dep" ;;
            *.py) inst_simple "$dep" ;;
            *) inst "$dep" ;;
        esac
    done

    # support for specific architectures
    case "$(uname -m)" in
        s390*)
            inst "/usr/sbin/lshmc"
            inst "/usr/bin/hmcdrvfs"
            inst "$moddir/anaconda-hmcroot" "/sbin/anaconda-hmcroot"
        ;;
    esac
}

# revert back to the default in case this is sourced
set +eu +o pipefail
