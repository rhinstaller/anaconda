#!/bin/sh
[ -e /run/install/DD-1 -o -e /tmp/DD-net ] || return 0

# regenerate modules.* files
depmod -b $NEWROOT
