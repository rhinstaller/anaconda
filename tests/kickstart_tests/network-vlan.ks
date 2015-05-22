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
CONTENT=$(cat /etc/sysconfig/network-scripts/$(ls /etc/sysconfig/network-scripts/ | grep ".150"))
DEVICE=$(sed -n 's/^PHYSDEV=//p' <<< "$CONTENT")

echo "$CONTENT" > /root/IFCFG_FILE
echo "$DEVICE" > /root/DEVICE_NAME

if [[ $CONTENT == "" ]]; then
   echo "ERROR: ifcfg file for vlan missing" >> /root/RESULT
   exit 0
fi

if [[ $CONTENT != *"BOOTPROTO=dhcp"* ]]; then
   echo "ERROR: BOOTPROTO is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"NAME=${DEVICE}.150"* ]]; then
   echo "ERROR: NAME is not present" >> /root/RESULT
fi

if [[ $CONTENT != *"DEVICE=${DEVICE}.150"* ]]; then
   echo "ERROR: DEVICE is not present" >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
   echo SUCCESS > /root/RESULT
fi
%end
