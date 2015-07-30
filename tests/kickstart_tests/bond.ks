url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --device=link --bootproto=dhcp

# Create testing bond interface
network --device=bond0 --bootproto=dhcp --bondslaves=link --activate

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

grep -q '^BOOTPROTO=dhcp$' $IF_FILE
if [[ $? -ne 0 ]]; then
   echo '*** BOOTPROTO is not present' >> /root/RESULT
fi

# No error was written to /root/RESULT file, everything is OK
if [[ ! -e /root/RESULT ]]; then
   echo SUCCESS > /root/RESULT
fi
%end
