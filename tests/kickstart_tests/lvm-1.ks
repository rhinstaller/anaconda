#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part /boot --fstype=ext4 --size=500
part pv.1 --fstype=lvmpv --size=4504
volgroup fedora pv.1
logvol swap --name=swap --vgname=fedora --size=500 --fstype=swap
logvol / --name=root --vgname=fedora --size=4000 --fstype=ext4

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
%end

%post
root_lv="/dev/mapper/fedora-root"
root_uuid="UUID=$(blkid -o value -s UUID $root_lv)"

# verify root lv is mounted at /mnt/sysimage
root_mount="$(grep ^$root_lv\\s/\\s /proc/mounts)"
if [ -z  "$root_mount" ]; then
    echo "*** lvm lv 'fedora-root' is not mounted at /" >> /root/RESULT
fi

root_fstype="$(echo $root_mount | cut -d' ' -f3)"
if [ $root_fstype != "ext4" ]; then
    echo "*** lvm lv 'fedora-root' does not contain an ext4 fs" >> /root/RESULT
fi

# verify root entry in /etc/fstab is correct
root_lv_entry="$(grep ^$root_lv\\s/\\s /etc/fstab)"
root_uuid_entry="$(grep ^$root_uuid\\s/\\s /etc/fstab)"
if [ -z "$root_lv_entry" -a -z "$root_uuid_entry" ] ; then
    echo "*** root lv is not the root entry in /etc/fstab" >> /root/RESULT
fi

# verify size of root lv
root_lv_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/root)
if [ $root_lv_size != "4000.00" ]; then
    echo "*** root lv has incorrect size" >> /root/RESULT
fi

# verify swap on lvm is active
swap_lv="/dev/mapper/fedora-swap"
swap_uuid="UUID=$(blkid -o value -s UUID $swap_lv)"
swap_dm="$(basename $(readlink $swap_lv))"
if ! grep -q $swap_dm /proc/swaps ; then
    echo "*** lvm lv 'fedora-swap' is not active as swap space" >> /root/RESULT
fi

# verify swap entry in /etc/fstab is correct
swap_lv_entry="$(grep ^$swap_lv\\sswap\\s /etc/fstab)"
swap_uuid_entry="$(grep ^$swap_uuid\\sswap\\s /etc/fstab)"
if [ -z "$swap_lv_entry" -a -z "$swap_uuid_entry" ] ; then
    echo "*** swap lv is not in /etc/fstab" >> /root/RESULT
fi

# verify size of swap lv
swap_lv_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/swap)
if [ $swap_lv_size != "500.00" ]; then
    echo "*** swap lv has incorrect size" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi

%end
