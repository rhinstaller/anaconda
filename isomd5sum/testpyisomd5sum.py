#!/usr/bin/python

import os
import pyisomd5sum

# create iso file
os.system("mkisofs -quiet . > testiso.iso")

# implant it
print "Implanting -> ", pyisomd5sum.implantisomd5sum("testiso.iso", 1, 0)

# do it again without forcing, should get error
print "Implanting again w/o forcing -> ", pyisomd5sum.implantisomd5sum("testiso.iso", 1, 0)

# do it again with forcing, should work
print "Implanting again forcing -> ", pyisomd5sum.implantisomd5sum("testiso.iso", 1, 1)

# check it
print "Checking -> ",pyisomd5sum.checkisomd5sum("testiso.iso")

# clean up
os.unlink("testiso.iso")
