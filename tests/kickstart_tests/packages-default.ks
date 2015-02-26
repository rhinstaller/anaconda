#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp --device=eth0

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part --fstype=ext4 --size=4400 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages --default
%end

%post
rpm -q fedora-release
if [ $? -eq 0 ]; then
    echo SUCCESS > /root/RESULT
else
    echo '*** fedora-release package was not installed' > /root/RESULT
fi
%end
