#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages --multilib
@container-management
@core
@domain-client
@hardware-support
@headless-management
@server-product
@standard
%end

%post
rpm -q fedora-release
if [ -e /usr/lib/libc.so.6 ]; then
    echo SUCCESS > /root/RESULT
else
    echo '*** no 32-bit libc package installed' > /root/RESULT
fi
%end
