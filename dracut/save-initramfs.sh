#!/bin/sh
# save-initramfs - save a copy of initramfs for shutdown/eject, if needed

command -v config_get >/dev/null || . /lib/anaconda-lib.sh
initramfs=""

# First, check to see if we can find a copy of initramfs laying around
for i in images/pxeboot/initrd.img ppc/ppc64/initrd.img images/initrd.img; do
    [ -f $repodir/$i ] && initramfs=$repodir/$i && break
done


# If we didn't find an initramfs image, save a copy of it
if [ -z "$initramfs" ]; then
    initramfs=/run/initramfs/initramfs-saved.cpio.gz
    gzip=$(type -P pigz || type -P gzip)
    # Prune out things we don't need - modules & firmware, python, overlay file
    find / -xdev | \
      grep -Ev 'lib/modules|lib/firmware|python|overlay|etc/ssl|fsck' | \
      cpio -co 2>/dev/null | $gzip -c1 > $initramfs
fi


# Make sure dracut-shutdown.service can find the initramfs later.
mkdir -p $NEWROOT/boot
ln -s $initramfs $NEWROOT/boot/initramfs-$(uname -r).img
# NOTE: $repodir must also be somewhere under /run for this to work correctly
