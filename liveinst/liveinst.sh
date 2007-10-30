#!/bin/sh
#
# Simple script to kick off an install from a live CD
#

if [ -z "$LIVE_BLOCK" ]; then
    if [ -b "/dev/mapper/live-osimg-min" ]; then
	LIVE_BLOCK="/dev/mapper/live-osimg-min"
    else
	LIVE_BLOCK="/dev/live-osimg"
    fi
fi

if [ ! -b $LIVE_BLOCK ]; then
  zenity --error --title="Not a Live image" --text "Can't do live image installation unless running from a live image"
  exit 1
fi

# load modules that would get loaded by the loader... (#230945)
for i in md raid0 raid1 raid5 raid6 raid456 raid10 fat msdos lock_nolock gfs2 reiserfs jfs xfs dm-mod dm-zero dm-mirror dm-snapshot dm-multipath dm-round-robin dm-emc vfat ; do /sbin/modprobe $i ; done

export ANACONDA_PRODUCTNAME="Fedora"
export ANACONDA_PRODUCTVERSION=$(rpm -q fedora-release --qf "%{VERSION}")
export ANACONDA_BUGURL="https://bugzilla.redhat.com/bugzilla/"

export PATH=/sbin:/usr/sbin:$PATH

if [ -z "$LANG" ]; then 
  LANG="en_US.UTF-8"
fi

# eventually, we might want to allow a more "normal" install path
ANACONDA="/usr/sbin/anaconda --method=livecd://$LIVE_BLOCK --lang $LANG"

if [ -x /usr/sbin/setenforce -a -e /selinux/enforce ]; then
    current=$(cat /selinux/enforce)
    /usr/sbin/setenforce 0
fi

/usr/sbin/swapoff -a
/sbin/lvm vgchange -an --ignorelockingfailure

if [ -x /usr/bin/hal-lock -a -e /var/lock/subsys/haldaemon ]; then
    /usr/bin/hal-lock --interface org.freedesktop.Hal.Device.Storage --exclusive --run "$ANACONDA"
else
    $ANACONDA
fi

if [ -n $current ]; then
    /usr/sbin/setenforce $current
fi
