#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
clearpart --all --initlabel

part raid.01 --size=500 --ondisk=sda --asprimary
part raid.02 --size=500 --ondisk=sdb --asprimary
part raid.11 --size=4000 --ondisk=sda
part raid.12 --size=4000 --ondisk=sdb
part raid.21 --size=1024 --ondisk=sda
part raid.22 --size=1024 --ondisk=sdb

# Yes, using 0,1,2 is wrong, but /proc/mounts uses /dev/mdX not /dev/md/X
raid /boot --level=1 --device=0 --fstype=ext4 raid.01 raid.02
raid swap  --level=1 --device=1 --fstype=swap raid.21 raid.22
raid /     --level=1 --device=2 --fstype=ext4 --label=rootfs raid.11 raid.12

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
%end

%post
# Verify the / raid level
root_raidlevel="$(grep ^md2.*active\\sraid1 /proc/mdstat)"
if [ -z  "$root_raidlevel" ]; then
    echo "*** mdraid 'root' is not a RAID1" >> /root/RESULT
fi

root_md="/dev/md2"
root_uuid="UUID=$(blkid -o value -s UUID $root_md)"

# verify root md is mounted at /mnt/sysimage
root_mount="$(grep ^$root_md\\s/\\s /proc/mounts)"
if [ -z  "$root_mount" ]; then
    echo "*** mdraid 'root' is not mounted at /" >> /root/RESULT
fi

root_fstype="$(echo $root_mount | cut -d' ' -f3)"
if [ $root_fstype != "ext4" ]; then
    echo "*** mdraid 'root' does not contain an ext4 fs" >> /root/RESULT
fi

# verify root entry in /etc/fstab is correct
root_md_entry="$(grep ^$root_md\\s/\\s /etc/fstab)"
root_uuid_entry="$(grep ^$root_uuid\\s/\\s /etc/fstab)"
if [ -z "$root_md_entry" -a -z "$root_uuid_entry" ] ; then
    echo "*** root md is not the root entry in /etc/fstab" >> /root/RESULT
fi

# Verify the swap raid level
swap_raidlevel="$(grep ^md1.*active\\sraid1 /proc/mdstat)"
if [ -z  "$swap_raidlevel" ]; then
    echo "*** mdraid 'swap' is not a RAID1" >> /root/RESULT
fi

# verify swap on md is active
swap_md="/dev/md1"
swap_uuid="UUID=$(blkid -o value -s UUID $swap_md)"
if ! grep -q $swap_md /proc/swaps ; then
    echo "*** mdraid 'swap' is not active as swap space" >> /root/RESULT
fi

# verify swap entry in /etc/fstab is correct
swap_md_entry="$(grep ^$swap_md\\sswap\\s /etc/fstab)"
swap_uuid_entry="$(grep ^$swap_uuid\\sswap\\s /etc/fstab)"
if [ -z "$swap_md_entry" -a -z "$swap_uuid_entry" ] ; then
    echo "*** swap md is not in /etc/fstab" >> /root/RESULT
fi

# Verify the boot raid level
boot_raidlevel="$(grep ^md0.*active\\sraid1 /proc/mdstat)"
if [ -z  "$boot_raidlevel" ]; then
    echo "*** mdraid 'boot' is not a RAID1" >> /root/RESULT
fi

boot_md="/dev/md0"
boot_uuid="UUID=$(blkid -o value -s UUID $boot_md)"

# verify boot md is mounted at /mnt/sysimage/boot
boot_mount="$(grep ^$boot_md\\s/boot\\s /proc/mounts)"
if [ -z "$boot_mount" ]; then
    echo "*** mdraid 'boot' is not mounted at /boot" >> /root/RESULT
fi

boot_fstype="$(echo $boot_mount | cut -d' ' -f3)"
if [ $boot_fstype != "ext4" ]; then
    echo "*** mdraid 'boot' does not contain an ext4 fs" >> /root/RESULT
fi

# verify boot entry in /etc/fstab is correct
boot_md_entry="$(grep ^$boot_md\\s/boot\\s /etc/fstab)"
boot_uuid_entry="$(grep ^$boot_uuid\\s/boot\\s /etc/fstab)"
if [ -z "$boot_md_entry" -a -z "$boot_uuid_entry" ] ; then
    echo "*** boot md is not the root entry in /etc/fstab" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
