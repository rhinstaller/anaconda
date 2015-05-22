url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --device=link --bootproto=dhcp

# Create testing bond interface
network --device=bond0 --bootproto=static --bondslaves=link --ip=192.168.1.1 --netmask=255.255.252.0 --gateway=192.168.1.2 --nameserver=192.168.1.3 --activate

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
IF_FILE='/etc/sysconfig/network-scripts/ifcfg-bond0'

if [[ -e $IF_FILE ]]; then
   cp $IF_FILE /root/
else
   echo '*** ifcfg file for bond interface missing' >> /root/RESULT
   exit 0
fi

grep -q '^DEVICE=bond0$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** DEVICE is not present' >> /root/RESULT
fi

grep -q '^TYPE=Bond$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** TYPE is not present' >> /root/RESULT
fi

grep -q '^ONBOOT=yes$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** ONBOOT is not present' >> /root/RESULT
fi

grep -q '^IPADDR=192.168.1.1$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** IPADDR is not present' >> /root/RESULT
fi

grep -q '^PREFIX=22$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** PREFIX is not present' >> /root/RESULT
fi

grep -q '^GATEWAY=192.168.1.2$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** GATEWAY is not present' >> /root/RESULT
fi

grep -q '^DNS1=192.168.1.3$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** DNS1 is not present' >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
   echo SUCCESS > /root/RESULT
fi
%end
