#!/bin/sh
# NFS mount can sometimes cause a hang, a delay, or a timeout problem after
# switching root, since it needs to survive the network reconfiguration in
# stage2 phase. So, it's better to umount the unneeded NFS mounts before
# switching root.

# When rd.live.ram boot parameter, the stage2 image is copied into memory
# from the NFS repository. So, keeping NFS mount is not required after
# the copy. The NFS repository can be mounted in the stage2 phase of package
# installation if needed.

type getargbool >/dev/null 2>&1 || . /lib/dracut-lib.sh

if getargbool 0 rd.live.ram -d -y live_ram; then
    while read -r src mnt fs rest || [ -n "$src" ]; do
        if [ "$mnt" = "/run/install/repo" ]; then
            if [ "$fs" = "nfs" ] || [ "$fs" = "nfs4" ]; then
                umount /run/install/repo
                break
            fi
        fi
        # inst.repo=nfs://dvd.iso case
        if [ "$mnt" = "/run/install/isodir" ]; then
            if [ "$fs" = "nfs" ] || [ "$fs" = "nfs4" ]; then
                umount /run/install/repo
                umount /run/install/isodir
                break
            fi
        fi
    done < /proc/mounts
fi
