#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide&arch=$basearch
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
