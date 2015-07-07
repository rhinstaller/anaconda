#version=DEVEL
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp

keyboard us
lang en_US.UTF-8
timezone America/New_York --utc
rootpw testcase
shutdown

bootloader --timeout=1
zerombr
clearpart --all
autopart

driverdisk /dev/disk/by-label/TEST_DD

%packages
@core
%end

%post --nochroot
SYSROOT=${ANA_INSTALL_PATH:-/mnt/sysimage}
RESULTFILE=$SYSROOT/root/RESULT
fail() { echo "*** $*" >> $RESULTFILE; }

# check the installer environment
[ -f /lib/modules/`uname -r`/updates/fake-dd.ko ] || fail "kmod not loaded"
[ -f /usr/bin/fake-dd-bin ] || fail "installer-enhancement not loaded"

# check the installed system
[ -f $SYSROOT/root/fake-dd-2.ko ] || fail "kmod rpm not installed"
[ ! -f $SYSROOT/usr/bin/fake-dd-bin ] || \
    fail "installer-enhancement package installed to target system"

# write successful result if nothing failed
if [[ ! -e $RESULTFILE ]]; then
    echo SUCCESS > $RESULTFILE
fi
%end
