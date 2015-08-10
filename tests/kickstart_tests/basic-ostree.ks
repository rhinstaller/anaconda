# Substitute something in for REPO or this will all come crashing down.
ostreesetup --nogpg --osname=fedora-atomic --remote=fedora-atomic --url=REPO --ref=fedora-atomic/rawhide/x86_64/base/core
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

%post --nochroot
mkdir -p /mnt/sysimage/root/
echo SUCCESS > /mnt/sysimage/root/RESULT
%end
