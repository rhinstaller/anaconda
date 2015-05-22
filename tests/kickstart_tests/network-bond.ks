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
CONTENT=$(cat /etc/sysconfig/network-scripts/ifcfg-bond0)

printf $CONTENT > /root/IFCFG

if [[ $CONTENT == "" ]]; then
   echo "ERROR: ifcfg file for bond interface missing" > /root/RESULT
   exit 0
fi

if [[ $CONTENT != *"DEVICE=bond0"* ]]; then
   echo "ERROR: DEVICE is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"TYPE=Bond"* ]]; then
   echo "ERROR: TYPE is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"ONBOOT=yes"* ]]; then
   echo "ERROR: ONBOOT is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"IPADDR=192.168.1.1"* ]]; then
   echo "ERROR: IPADDR is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"PREFIX=22"* ]]; then
   echo "ERROR: PREFIX is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"GATEWAY=192.168.1.2"* ]]; then
   echo "ERROR: GATEWAY is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"DNS1=192.168.1.3"* ]]; then
   echo "ERROR: DNS1 is not present" >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
   echo SUCCESS > /root/RESULT
fi
%end
