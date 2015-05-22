url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --device=link --bootproto=dhcp
# Create testing vlan interface
network --device=link --vlanid=150 --bootproto=dhcp

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
IF_FILE=$(ls /etc/sysconfig/network-scripts/*.150)
DEVICE=$(sed 's/.*-//g' <<< "$IF_FILE")

if [[ -e $IF_FILE ]]; then
   cp $IF_FILE /root/
   echo "$DEVICE" >> /root/device
else
   echo '*** ifcfg file for vlan missing' >> /root/RESULT
   exit 0
fi

grep -q '^TYPE=Vlan$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** TYPE=Vlan is not present' >> /root/RESULT
fi

grep -q '^BOOTPROTO=dhcp$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** BOOTPROTO is not present' >> /root/RESULT
fi

grep -q "^NAME=${DEVICE}$" $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** NAME is not present' >> /root/RESULT
fi

grep -q "^DEVICE=${DEVICE}$" $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** DEVICE is not present' >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
   echo SUCCESS > /root/RESULT
fi
%end
