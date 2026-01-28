The list-harddrives script
==========================

:Authors:
   Martin Kolman <mkolman@redhat.com>

Introduction
------------

The list-harddrives script is primarily meant for use in the
kickstart %post scriptlets for listing all individual harddrives
on the system.


Output format
-------------

The list-harddrives script outputs two values per line separated
by a single whitespace:
- the device node name (eq. sda for /dev/sda)
- the size in MB as a floating point number
It does this for each individual harddrive on the system.

Example output:

sda 61057.3359375
sdb 476940.023438
sdc 30524.0


What devices are not listed
---------------------------

The list harddrives script will not list:
- CD/DVD drives (/dev/sr*)
- zram block devices
- software RAID (/dev/md*)
- all device mapper devices
- anything that is not a block device
