#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard en
lang en
timezone America/New_York --utc
rootpw testcase

# Test services
services --disabled=sshd --enabled=systemd-timesyncd

# Test SELinux
selinux --enforcing

shutdown

%packages
%end

%post

# Test enabled
systemctl is-enabled systemd-timesyncd
if [[ $? -ne 0 ]]; then
    echo "*** systemd-timesyncd is disabled, not enabled" >> /root/RESULT
fi

# Test disabled
systemctl is-enabled sshd
if [[ $? -eq 0 ]]; then
    echo "*** sshd is enabled, not disabled" >> /root/RESULT
fi

# Test disabled - W/out change
systemctl is-enabled systemd-networkd
if [[ $? -eq 0 ]]; then
    echo "*** systemd-networkd is enabled, should be disabled" >> /root/RESULT
fi

# SELinux test
grep 'SELINUX=enforcing' /etc/selinux/config
if [[ $? -ne 0 ]]; then
    echo "*** SELinux not in enforcing mode" >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
