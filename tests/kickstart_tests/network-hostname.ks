url --url=ftp://mirror.utexas.edu/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp
# Set hostname for testing
network --hostname=testhostname.example.com

bootloader --timeout=1
zerombr
clearpart --all
part --fstype=ext4 --size=4400 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
%end

%post
# Check if hostname is set to the system
if [ `hostname` = "testhostname.example.com" ]; then
    echo SUCCESS > /root/RESULT
else
    echo FAILURE > /root/RESULT
fi
%end
