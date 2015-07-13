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

shutdown

%packages
%end

%post

# Test enabled
systemctl is-enabled systemd-timesyncd | grep enabled
if [[ $? -ne 0 ]]; then
    echo "*** systemd-timesyncd is disabled, not enabled" >> /root/RESULT
fi

# Test disabled
systemctl is-enabled sshd | grep disabled
if [[ $? -ne 0 ]]; then
    echo "*** sshd is enabled, not disabled" >> /root/RESULT
fi

# Test disabled - W/out change
systemctl is-enabled systemd-networkd | grep disabled
if [[ $? -ne 0 ]]; then
    echo "*** systemd-networkd is enabled, should be disabled" >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
