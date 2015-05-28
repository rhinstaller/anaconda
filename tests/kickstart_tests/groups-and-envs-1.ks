url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all
autopart

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
@core
@c-development
@^web-server-environment
%end

%post
# We don't have a way of determining if a group/env is installed or not.
# These sentinel packages will have to do.
rpm -q httpd
if [[ $? != 0 ]]; then
    echo '*** web-server-environment was not installed' > /root/RESULT
else
    rpm -q gcc
    if [[ $? != 0 ]]; then
        echo '*** c-development was not installed' > /root/RESULT
    else
        echo SUCCESS > /root/RESULT
    fi
fi
%end
