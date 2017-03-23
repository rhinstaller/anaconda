#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard --vckeymap cz --xlayouts=cz
lang cs_CZ.UTF-8
timezone America/New_York --utc
rootpw testcase

# SeLinux test
selinux --disabled

shutdown

%packages
%end

%post

# Test disabled
cat /etc/selinux/config | grep SELINUX=disabled
if [[ $? -ne 0 ]]; then
    echo "*** SELinux not disabled" >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
