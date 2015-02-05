url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all
part --fstype=ext4 --size=6500 /
part --fstype=ext4 --size=500 /boot
part --fstype=swap --size=500 swap

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

%packages
@^xfce-desktop-environment

# (1) Test that you can remove a package that's part of a group
@c-development
-valgrind

# (2) Test that you can add and then remove the same package.
qemu-kvm
-qemu-kvm

# (3) Test that you can add packages with a glob.
emacs*

# (4) Test that you can remove packages with a glob.
-ibus*
%end

%post
# We don't have a way of determining if a group/env is installed or not.
# These sentinel packages will have to do.

# Testing #1 - gcc should be installed, but not valgrind
rpm -q gcc
if [[ $? != 0 ]]; then
    echo '*** c-development group was not installed' > /root/RESULT
    exit 1
fi

rpm -q valgrind
if [[ $? == 0 ]]; then
    echo '*** valgrind package should not have been installed' > /root/RESULT
    exit 1
fi

# Testing #2 - qemu-kvm should not be installed.
rpm -q qemu-kvm
if [[ $? == 0 ]]; then
    echo '*** 3d-printing group should not have been installed' > /root/RESULT
    exit 1
fi

# Testing #3 - emacs stuff should be installed.
rpm -qa emacs\*
if [[ $? != 0 ]]; then
    echo '*** emacs glob was not installed' > /root/RESULT
    exit 1
fi

# Make sure that more than just emacs and its dependencies were installed.
count=$(rpm -qa emacs\* | wc -l)
if [[ $count -lt 50 ]]; then
    echo '*** emacs glob was not fully installed' > /root/RESULT
    exit 1
fi

# Testing #4 - ibus stuff should not be installed.
rpm -qa ibus\*
if [[ $? == 0 ]]; then
    echo '*** ibus glob should not have been installed' > /root/RESULT
    exit 1
fi

echo SUCCESS > /root/RESULT
%end
