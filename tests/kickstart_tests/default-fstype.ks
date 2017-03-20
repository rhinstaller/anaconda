#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part /boot --size=500 --label=boot
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
root_fstype=$(blkid -o value -t LABEL=root -s TYPE)
if [ $root_fstype != "ext4" ]; then
    echo "default fstype is incorrect (got $root_fstype; expected ext4)" >> /root/RESULT
fi

boot_fstype=$(blkid -o value -t LABEL=boot -s TYPE)
if [ $boot_fstype != "ext4" ]; then
    echo "default boot fstype is incorrect (got $boot_fstype; expected ext4)" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
