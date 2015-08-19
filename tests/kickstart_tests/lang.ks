#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard us
lang cs_CZ.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
@core
%end

%post
LANG="cs_CZ.UTF-8"

INSTLANG=`cat /etc/locale.conf | awk -F\" '{ print $2 }'`

if [[ "$INSTLANG" != "$LANG" ]]; then
    echo '*** specified language was not set' >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
