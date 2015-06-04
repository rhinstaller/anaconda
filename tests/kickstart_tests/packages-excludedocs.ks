#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
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

%packages --excludedocs
@container-management
@core
@domain-client
@hardware-support
@headless-management
@server-product
@standard
%end

%post
if [ ! -d /usr/share/doc ]; then
    echo SUCCESS > /root/RESULT
else
    cd /usr/share/doc
    count=$(find . -type f | grep -v -E "^\.$" | wc -l)

    if [ $count -eq 0 ]; then
        dirs=$(find . -type d | grep -v -E "^\.$" | wc -l)

        if [ $dirs -eq 0 ]; then
            echo SUCCESS > /root/result
        else
            echo "SUCCESS - but directories still exist under /usr/share/doc" > /root/RESULT
        fi
    else
        echo "there are files in /usr/share/doc" > /root/RESULT
        echo >> /root/RESULT
        find /usr/share/doc >> /root/RESULT
    fi
fi
%end
