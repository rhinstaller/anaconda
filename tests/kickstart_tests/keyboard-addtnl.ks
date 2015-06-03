#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard --vckeymap cz --xlayouts=cz,fi
lang cs_CZ.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

%packages
@core
%end

%post
VCKBD="cz"
XKBD="cz,fi"

KBD=`grep KEYMAP /etc/vconsole.conf | awk -F\" '{ print $2 }'`
echo "$KBD"

if [[ "$KBD" != "$VCKBD" ]]; then
    echo '*** specified vconsole keyboard was not set' >> /root/RESULT
fi

ADDTNL=`grep XkbLayout /etc/X11/xorg.conf.d/00-keyboard.conf | awk -F\" '{ print $4 }'`
echo "$ADDTNL"

if [[ "$ADDTNL" != "$XKBD" ]]; then
    echo '*** specified xlayout(s) not set' >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
