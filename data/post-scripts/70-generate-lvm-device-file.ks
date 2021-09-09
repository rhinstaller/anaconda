# Generate LVM devices file
# /etc/lvm/devices/system.devices
# This is a temporary workaround and should be reverted once blivet supports
# manipulation of the file.
# See: https://bugzilla.redhat.com/show_bug.cgi?id=2002550

%post

[ -e /usr/sbin/vgimportdevices ] && vgimportdevices -a

%end
