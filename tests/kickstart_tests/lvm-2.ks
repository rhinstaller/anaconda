#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part /boot --fstype=ext4 --size=500
part pv.1 --fstype=lvmpv --size=5000
volgroup fedora pv.1
logvol swap --name=swap --vgname=fedora --percent=10 --fstype=swap
logvol / --name=root --vgname=fedora --percent=90 --fstype=ext4

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
python
%end

%post
# verify sizes of lvs match percentages specified
vg_size=$(vgs --noheadings -o size --unit=m --nosuffix fedora)
root_lv_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/root)
swap_lv_size=$(lvs --noheadings -o size --unit=m --nosuffix fedora/swap)
root_percentage=$(python -c "print int(round(($root_lv_size*100)/$vg_size))")
swap_percentage=$(python -c "print int(round(($swap_lv_size*100)/$vg_size))")
if [ $swap_percentage != "10" ]; then
    echo "*** swap lv size is incorrect ($swap_lv_size MiB, or ${swap_percentage}%)" >> /root/RESULT
fi

if [ $root_percentage != "90" ]; then
    echo "*** root lv size is incorrect ($root_lv_size MiB, or ${root_percentage}%)" >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi

%end
