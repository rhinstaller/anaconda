#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide&arch=$basearch
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel

reqpart --add-boot
part pv.1 --fstype=lvmpv --size=4504
volgroup fedora pv.1
logvol swap --name=swap --vgname=fedora --size=500 --fstype=swap
logvol / --name=root --vgname=fedora --size=4000 --label=root

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
%end

%post
# FIXME: This will need to test for other things one day when we support tests on other arches
boot_mount="$(grep /mnt/sysimage/boot /proc/mounts)"
if [ -z "${boot_mount}" ]; then
    echo "*** no /boot mount point was created by reqpart" >> /root/RESULT
fi

# Also verify the partitions we explicitly asked for got made.
root_fstype=$(blkid -o value -t LABEL=root -s TYPE)
if [ "${root_fstype}" != "ext4" ]; then
    echo "default fstype is incorrect (got $root_fstype; expected ext4)" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
