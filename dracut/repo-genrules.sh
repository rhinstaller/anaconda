#!/bin/sh
# generate udev rules for handling anaconda-specific root devices
# (just the disk-based ones - the network ones are done by netroot)

case "$root" in
  anaconda-disk:*)
    # anaconda-disk:<device>[:<path>]
    strsep ":" "$root" f diskdev diskpath
    diskdev=$(disk_to_dev_path $diskdev)
    when_diskdev_appears "$diskdev" \
        "/sbin/anaconda-diskroot $diskdev $diskpath"
  ;;
  anaconda-auto-cd)
    # special catch-all rule for CDROMs
    echo 'ENV{ID_CDROM}=="1",' \
           'RUN+="/sbin/initqueue --settled --onetime --unique' \
             '/sbin/anaconda-diskroot $env{DEVNAME}"\n' >> $rulesfile
  ;;
esac

# Make sure we wait for the dmsquash root device to appear
case "$root" in
    anaconda-*) wait_for_dev /dev/root ;;
esac
