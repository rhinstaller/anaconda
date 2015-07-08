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
timezone Europe/Prague
rootpw testcase

shutdown

%packages
%end

%post
## UTC ZONE TEST
# hwclock LOCAL test
hwclock -D | grep "Assuming hardware clock is kept in local time."
if [[ $? -ne 0 ]]; then
    echo "*** hwclock not set to LOCAL time." >> /root/RESULT
fi

# cat adjtime LOCAL test
cat /etc/adjtime | grep LOCAL
if [[ $? -ne 0 ]]; then
    echo "*** Time in /etc/adjtime is not set to LOCAL." >> /root/RESULT
fi

# everything passes
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
