url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all

part --fstype=ext4 --size=4400 --label=rootfs /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap
part --fstype=tmpfs --size 5000 /tmp

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
@core
%end

%post
mount | grep -q "tmpfs on /tmp"
if [[ $? != 0 ]]; then
    echo '*** tmpfs not mounted in /tmp' >> /root/RESULT
fi

mount | grep "tmpfs on /tmp" | grep -q "size=5120000k"
if [[ $? != 0 ]]; then
    echo '*** tmpfs size is not 5000 MB' >> /root/RESULT
fi

cat /etc/fstab | grep -q "tmpfs"
if [[ $? != 0 ]]; then
    echo '*** tmpfs is not present in fstab' >> /root/RESULT
fi

cat /etc/fstab | grep "tmpfs" | grep -q "size=5000m"
if [[ $? != 0 ]]; then
    echo '*** tmpfs size is not 5000 MB in fstab' >> /root/RESULT
fi

# the installation was successfull if nothing bad happend till now
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
