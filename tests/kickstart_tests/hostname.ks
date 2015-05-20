url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp
# Set hostname for testing
network --hostname=testhostname.example.com

bootloader --timeout=1
zerombr
clearpart --all
part --fstype=ext4 --size=4400 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
%end

%post
HOSTNAME="testhostname.example.com"

# Check if hostname is set to the system
grep -q "^${HOSTNAME}$" /etc/hostname
if [[ $? -ne 0 ]]; then
    echo '*** hostname is not set to /etc/hostname' >> /root/RESULT
fi

hostnamectl --static | grep -q "^${HOSTNAME}$"
if [[ $? -ne 0 ]]; then
    echo '*** hostnamectl --static does not return correct hostname' >> /root/RESULT
fi

if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
