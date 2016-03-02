#!/bin/bash
# Set up a launcher on the desktop for the live installer if we're on
# a live CD

# Prevents breakage if the hostname is changed before or during the install
# Also lets us run (with the X11 backend) on Wayland
[ -x /usr/bin/xhost ] && xhost +si:localuser:root > /dev/null 2>&1

# don't run on geode (olpc)
if [ `grep -c Geode /proc/cpuinfo` -eq 0 ]; then
  if [ -b /dev/mapper/live-osimg-min ]; then
    test -f ${XDG_CONFIG_HOME:-~/.config}/user-dirs.dirs && source ${XDG_CONFIG_HOME:-~/.config}/user-dirs.dirs
    cp /usr/share/applications/liveinst.desktop "${XDG_DESKTOP_DIR:-$HOME/Desktop}"
  elif [ -f /.livecd-configured ]; then  # FIXME: old way... this should go away
    test -f ${XDG_CONFIG_HOME:-~/.config}/user-dirs.dirs && source ${XDG_CONFIG_HOME:-~/.config}/user-dirs.dirs
    cp /usr/share/applications/liveinst.desktop "${XDG_DESKTOP_DIR:-$HOME/Desktop}"
  fi
fi
