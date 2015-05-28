#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
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

%packages
@container-management
@core
@domain-client
@hardware-support
@headless-management
@server-product
@standard
%end

%post
rpm -q fedora-release-server
if [ $? -eq 0 ]; then
    echo SUCCESS > /root/RESULT
else
    echo '*** Fedora Server default environment was not installed' > /root/RESULT
fi
%end
