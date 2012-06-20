#!/bin/sh
# anaconda-pre-trigger.sh: set udev properties before the rules run

# THIS! IS! ANACONDA!!!
udevproperty ANACONDA=1
# (used in udev rules to keep stuff like mdadm, multipath, etc. out of our way)
