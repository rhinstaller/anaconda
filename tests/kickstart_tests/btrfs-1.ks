url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all

part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap
part btrfs.10 --fstype="btrfs" --size=4400

btrfs none --label=fedora-btrfs btrfs.10

btrfs / --subvol --name=root fedora-btrfs
btrfs /home --subvol --name=home fedora-btrfs

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
@core
%end

%post
btrfs filesystem show fedora-btrfs
if [[ $? != 0 ]]; then
    echo "*** btrfs volume 'fedora-btrfs' was not found" >> /root/RESULT
fi

grep "\s/\s" /etc/fstab | grep "subvol=root"
if [[ $? != 0 ]]; then
    echo "*** root subvol is not mounted at /" >> /root/RESULT
fi

grep "\s/home\s" /etc/fstab | grep "subvol=home"
if [[ $? != 0 ]]; then
    echo "*** home subvol is not mounted at /home" >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
