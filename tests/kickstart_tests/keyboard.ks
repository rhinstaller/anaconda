#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch
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
shutdown

%packages
@core
%end

%post
INSTKBD="cz"
KBD=`grep KEYMAP /etc/vconsole.conf | awk -F\" '{ print $2 }'`
echo "$KBD"

if [[ "$KBD" != "$INSTKBD" ]]; then
    echo '*** specified keyboard was not set' >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
