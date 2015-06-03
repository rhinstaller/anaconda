#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

# use ntp.cesnet.cz as an NTP server and 0.pool.ntp.org as an NTP pool
timezone --utc --ntpservers=ntp.cesnet.cz,0.pool.ntp.org,0.pool.ntp.org,0.pool.ntp.org,0.pool.ntp.org Europe/Prague

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
# server 0.fedora.pool.ntp.org iburst
egrep '^\s*server\s*ntp\.cesnet\.cz\s*[a-zA-Z]+\s*$' /etc/chrony.conf
if [ $? -ne 0 ]; then
    echo '*** ntp.cesnet.cz not configured as an NTP server' >> /root/RESULT
fi

egrep '^\s*pool\s*0\.pool\.ntp\.org\s*[a-zA-Z]+\s*$' /etc/chrony.conf
if [ $? -ne 0 ]; then
    echo '*** 0.pool.ntp.org not configured as an NTP pool' >> /root/RESULT
fi

if [ ! -e /root/RESULT ]; then
   echo SUCCESS > /root/RESULT
fi
%end
