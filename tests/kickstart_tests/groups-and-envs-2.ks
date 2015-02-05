url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/
install
network --bootproto=dhcp

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
# (1) Test that you can remove a group that's part of an environment.
@^xfce-desktop-environment
-@dial-up

# (2) Test that you can add and then remove a group.
@3d-printing
-@3d-printing

# (3) Test that --optional works.
@container-management --optional

# (4) Test that --nodefaults works.
@rpm-development-tools --nodefaults
%end

%post
# We don't have a way of determining if a group/env is installed or not.
# These sentinel packages will have to do.

# Testing #1 - lrzsz is only part of dial-up, and should not be installed.
rpm -q lrzsz
if [[ $? == 0 ]]; then
    echo '*** dial-up group should not have been installed' > /root/RESULT
    exit 1
fi

# Testing #2 - RepetierHost is only part of 3d-printing, and should not
# be installed.
rpm -q RepetierHost
if [[ $? == 0 ]]; then
    echo '*** 3d-printing group should not have been installed' > /root/RESULT
    exit 1
f

# Testing #3 - docker-registry is only part of container-management, where
# it is optional, so it should be installed.
rpm -q docker-registry
if [[ $? != 0 ]]; then
    echo '*** docker-registry was not installed' > /root/RESULT
    exit 1
fi

# Testing #4 - rpm-build is mandatory so it should be installed.  rpmdevtools is
# default so it should not.  rpmlint is optional so it should not.
rpm -q rpm-build
if [[ $? != 0 ]]; then
    echo '*** Mandatory package from rpm-development-tools was not installed' > /root/RESULT
    exit 1
else
    rpm -q rpmdevtools
    if [[ $? == 0 ]]; then
        echo '*** Default package from rpm-development-tools should not have been installed' > /root/RESULT
        exit 1
    else
        rpm -q rpmlint
        if [[ $? == 0 ]]; then
            echo '*** Optional package from rpm-development-tools should not have been installed' > /root/RESULT
            exit 1
        fi
    fi
fi

echo SUCCESS > /root/RESULT
%end
