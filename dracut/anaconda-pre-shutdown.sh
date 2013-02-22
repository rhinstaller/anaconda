# Fix mount loops that prevent unmount/eject.
#
# During startup, we mount our repo (e.g. the DVD) at $repodir or $isodir.
# We then mount the runtime image from that repo at /newroot and switch into it.
# Switching moves $repodir to /newroot/$repodir, which creates a mount loop:
#
# -> You can't unmount the runtime image because the DVD is mounted under it
# -> You can't unmount the DVD because it holds the mounted runtime image
#
# And now you can't unmount or eject the DVD!
#
# We fix this by moving the repo mounts back out from under the runtime image
# during shutdown. Then everything can be unmounted like normal.

. /lib/anaconda-lib.sh

for mnt in $repodir $isodir; do
    # systemd-shutdown puts old root at /oldroot
    oldmnt=/oldroot$mnt
    grep -qw $oldmnt /proc/mounts && mount --move $oldmnt $mnt
done
