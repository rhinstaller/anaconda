#!/bin/sh
# Transfer CA certificates imported in initramfs via kickstart
# to anaconda environment

./lib/anaconda-lib.sh

[ -d /run/install/certificates/path ] && copytree /run/install/certificates/path /sysroot
