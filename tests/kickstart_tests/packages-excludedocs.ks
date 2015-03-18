#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all --initlabel
part --fstype=ext4 --size=4400 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

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
    count=$(find . | grep -v -E "^\.$" | wc -l)
    if [ $count -eq 0 ]; then
        echo "SUCCESS - but the /usr/share/doc directory still exists" > /root/RESULT
    else
        echo "there are files and possibly directories in /usr/share/doc" > /root/RESULT
        echo >> /root/RESULT
        find /usr/share/doc >> /root/RESULT
    fi
fi
%end
