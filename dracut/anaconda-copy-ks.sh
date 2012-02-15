#!/bin/sh
# Copy over kickstart files from the initrd to the sysroot before pivot
cp /*cfg /*ks /sysroot/ 2> /dev/null
