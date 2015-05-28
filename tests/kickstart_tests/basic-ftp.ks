url --url=ftp://mirror.utexas.edu/pub/fedora/linux/development/$releasever/$basearch/os/
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

%post
# If we made it post, that's good enough
echo SUCCESS > /root/RESULT
%end
