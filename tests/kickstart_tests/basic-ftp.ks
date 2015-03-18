url --url=ftp://mirrors.kernel.org/fedora/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

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
# If we made it post, that's good enough
echo SUCCESS > /root/RESULT
%end
