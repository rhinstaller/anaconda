#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/$basearch/os/"
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
selinux --permissive

shutdown

%packages
%end

%post

# Test permissive
cat /etc/selinux/config | grep SELINUX=permissive
if [[ $? -ne 0 ]]; then
    echo "*** SELinux not in permissive mode" >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
