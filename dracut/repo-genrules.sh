#!/bin/sh
# generate udev rules for handling anaconda-specific root devices
# (just the disk-based ones - the network ones are done by netroot)

. /lib/anaconda-lib.sh

case "$root" in
  anaconda-disk:*)
    # anaconda-disk:<device>[:<path>]
    splitsep ":" "$root" f diskdev diskpath
    diskdev=$(disk_to_dev_path $diskdev)
    when_diskdev_appears $diskdev \
        anaconda-diskroot \$env{DEVNAME} $diskpath
  ;;
  anaconda-auto-cd)
    # special catch-all rule for CDROMs
    when_any_cdrom_appears \
        anaconda-diskroot \$env{DEVNAME}
    # HACK: anaconda demands that CDROMs be mounted at /mnt/install/source
    ln -s repo /run/install/source
  ;;
esac
