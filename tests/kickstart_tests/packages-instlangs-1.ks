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

# Only install the en_US locale
%packages --instLangs=en_US
%end

%post
# Make sure no non-english .mo files were installed
molist="$(find /usr/share/locale \( -name 'en' -type d -prune \) -o \( -name 'en[@_]*' -type d -prune \) -o \( -name '*.mo' -print \) )"
if [ -n "$molist" ]; then
    echo "*** non-en .mo files were installed" >> /root/RESULT
fi

# Check that the en_US locale was installed
localedef --list-archive | grep -a -q '^en_US$'
if [ $? != 0 ]; then
    echo "*** en_US was not installed" >> /root/RESULT
fi

# Check that only the en_US locale and related encodings were installed
# Use grep -a to force text mode, since sometimes a character will end up in the
# output that makes grep think it's binary
other_locales="$(localedef --list-archive | grep -a -v '^en_US$' | grep -a -v '^en_US\.')"
if [ -n "$other_locales" ]; then
    echo "*** non-en locales were installed" >> /root/RESULT
fi

if [ ! -f /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
