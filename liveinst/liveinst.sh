#!/bin/sh
#
# Simple script to kick off an install from a live CD
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
for i in md raid0 raid1 raid5 raid6 raid456 raid10 fat msdos lock_nolock gfs2 reiserfs ext2 ext3 jfs xfs dm-mod dm-zero dm-mirror dm-snapshot dm-multipath dm-round-robin dm-emc vfat ; do /sbin/modprobe $i ; done

export ANACONDA_PRODUCTNAME="Fedora"
export ANACONDA_PRODUCTVERSION=$(rpm -q fedora-release --qf "%{VERSION}")
export ANACONDA_BUGURL="https://bugzilla.redhat.com/bugzilla/"

export PATH=/sbin:/usr/sbin:$PATH

if [ -n "$DISPLAY" -a -n "$LANG" ]; then
    LANG="--lang $LANG"
fi

# eventually, we might want to allow a more "normal" install path
ANACONDA="/usr/sbin/anaconda --liveinst --method=livecd://$LIVE_BLOCK"

if [ -x /usr/sbin/setenforce -a -e /selinux/enforce ]; then
    current=$(cat /selinux/enforce)
    /usr/sbin/setenforce 0
fi

if [ ! -e /selinux/load ]; then
    ANACONDA="$ANACONDA --noselinux"
fi

/sbin/swapoff -a
/sbin/lvm vgchange -an --ignorelockingfailure

if [ -x /usr/bin/hal-lock -a -e /var/lock/subsys/haldaemon ]; then
    /usr/bin/hal-lock --interface org.freedesktop.Hal.Device.Storage --exclusive --run "$ANACONDA $*"
else
    $ANACONDA $*
fi

if [ -n "$current" ]; then
    /usr/sbin/setenforce $current
fi
