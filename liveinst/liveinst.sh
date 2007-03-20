#!/bin/sh
#
# Simple script to kick off an install from a live CD
#

if [ -z "$LIVE_MOUNT_PATH" ]; then
    LIVE_MOUNT_PATH="/mnt/livecd"
fi

if [ ! -f /.livecd-configured ]; then
  zenity --error --title="Not a Live CD" --text "Can't do live CD installation unless running on a live CD"
fi

export ANACONDA_PRODUCTNAME="Fedora"
export ANACONDA_PRODUCTVERSION=$(rpm -q fedora-release --qf "%{VERSION}")
export ANACONDA_BUGURL="https://bugzilla.redhat.com/bugzilla/"

export PATH=/sbin:/usr/sbin:$PATH

if [ -z "$LANG" ]; then 
  LANG="en_US.UTF-8"
fi

# eventually, we might want to allow a more "normal" install path
/usr/sbin/anaconda --method=livecd://$LIVE_MOUNT_PATH --lang $LANG
