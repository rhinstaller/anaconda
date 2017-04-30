url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all

part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap
part btrfs.10 --fstype="btrfs" --size=2200
part btrfs.12 --fstype="btrfs" --size=2200

btrfs none --data=raid0 --metadata=raid1 --label=fedora-btrfs btrfs.10 btrfs.12

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

btrfs fi df / | grep "Data,\sRAID0"
if [[ $? != 0 ]]; then
    echo "*** btrfs volume data RAID level is not RAID0" >> /root/RESULT
fi

btrfs fi df / | grep "Metadata,\sRAID1"
if [[ $? != 0 ]]; then
    echo "*** btrfs volume metadata RAID level is not RAID1" >> /root/RESULT
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
