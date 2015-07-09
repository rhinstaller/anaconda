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
shutdown

# TEST: firewall
firewall --enable --port=22001:tcp,6400:udp --service=tftp,smtp

%packages
%end

%post

## TEST PROCEDURE
# Test for 22001/TCP
firewall-offline-cmd --list-ports | grep 22001/tcp
if [[ $? -ne 0 ]]; then
    echo "*** Firewall config for 22001/tcp" >> /root/RESULT
fi

# Test for 6400/UDP
firewall-offline-cmd --list-ports | grep 6400/udp
if [[ $? -ne 0 ]]; then
    echo "*** Firewall config for 6400/udp failed" >> /root/RESULT
fi

# Test for service tftp
firewall-offline-cmd --list-services | grep tftp
if [[ $? -ne 0 ]]; then
    echo "*** Firewall service tftp not assigned" >> /root/RESULT
fi

# Test for service smtp
firewall-offline-cmd --list-services | grep smtp
if [[ $? -ne 0 ]]; then
    echo "*** Firewall service smtp not assigned" >> /root/RESULT
fi

# Test for service sane (disabled)
firewall-offline-cmd --list-services | grep sane
if [[ $? -ne 1 ]]; then
    echo "*** Firewall service sane enabled, should be disabled" >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
