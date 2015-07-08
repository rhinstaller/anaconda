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
timezone Europe/Prague --utc
rootpw testcase

shutdown

%packages
%end

%post
## UTC ZONE TEST
# hwclock -D UTC test
hwclock -D | grep "Assuming hardware clock is kept in UTC time."
if [[ $? -ne 0 ]]; then
    echo "*** hwclock not set to UTC.." >> /root/RESULT
fi

# cat adjtime UTC test
cat /etc/adjtime | grep UTC
if [[ $? -ne 0 ]]; then
    echo "*** Time in /etc/adjtime not set to UTC." >> /root/RESULT
fi

# everything passes
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
