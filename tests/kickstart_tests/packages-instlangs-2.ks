#version=DEVEL
url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide&arch=$basearch
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
autopart

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

# Install no locales
%packages --instLangs=
%end

%post
# Make sure no .mo files were installed
molist="$(find /usr/share/locale -name '*.mo')"
if [ -n "$molist" ]; then
    echo "*** .mo files were installed" >> /root/RESULT
fi

# Check that no locales were installed.
other_locales="$(localedef --list-archive)"
if [ -n "$other_locales" ]; then
    echo "*** locales were installed" >> /root/RESULT
fi

if [ ! -f /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
