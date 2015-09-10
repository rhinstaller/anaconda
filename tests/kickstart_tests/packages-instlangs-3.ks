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

# Install a short list of languages
# Use ones with translations in blivet to make them easy to find.
%packages --instLangs=es:fr:it
python3-blivet
%end

%post
# Make sure the locales we asked for are installed
if [ ! -f /usr/share/locale/es/LC_MESSAGES/blivet.mo ]; then
    echo "*** Spanish translations were not installed" >> /root/RESULT
fi

if [ ! -f /usr/share/locale/fr/LC_MESSAGES/blivet.mo ]; then
    echo "*** French translations were not installed" >> /root/RESULT
fi

if [ ! -f /usr/share/locale/it/LC_MESSAGES/blivet.mo ]; then
    echo "*** Italian translations were not installed" >> /root/RESULT
fi

# Make sure nothing else got installed
molist="$(find /usr/share/locale \( -name 'fr' -type d -prune \) -o \
          \( -name 'es' -type d -prune \) -o \
          \( -name 'it' -type d -prune \) -o \
	  -o \( -name 'blivet.mo' -print \) )"
if [ -n "$molist" ]; then
    echo "*** unrequested .mo files were installed" >> /root/RESULT
fi

# Check that the requested locales were installed
localedef --list-archive | grep -a -q '^es_'
if [ $? != 0 ]; then
    echo "*** es locales were not installed" >> /root/RESULT
fi

localedef --list-archive | grep -a -q '^fr_'
if [ $? != 0 ]; then
    echo "*** fr locales were not installed" >> /root/RESULT
fi

localedef --list-archive | grep -a -q '^it_'
if [ $? != 0 ]; then
    echo "*** it locales were not installed" >> /root/RESULT
fi

# Check that only the requested locales were installed
# Use grep -a to force text mode, since sometimes a character will end up in the
# output that makes grep think it's binary
other_locales="$(localedef --list-archive | grep -a -v '^fr_' | grep -a -v '^es_' | grep -a -v '^it_')"
if [ -n "$other_locales" ]; then
    echo "*** unrequested locales were installed" >> /root/RESULT
fi

if [ ! -f /root/RESULT ]; then
    echo SUCCESS > /root/RESULT
fi
%end
