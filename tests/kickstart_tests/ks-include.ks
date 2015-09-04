url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide&arch=$basearch
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
%end

# Include a kickstart that contains %post
%include KS-TEST-INCLUDE
