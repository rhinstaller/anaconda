#
# partitioning.py: partitioning and other disk management
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

if __name__ == "__main__":
    import sys
    sys.path.append ("isys")

import isys
import parted
import raid
import fsset
import os
import sys
import string
import iutil
import partedUtils
import raid
from constants import *
from flags import flags
from partErrors import *
import partRequests

from rhpl.translate import _

def partitionObjectsInitialize(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        anaconda.id.diskset.closeDevices()
        isys.flushDriveDict()
        return

    # read in drive info
    anaconda.id.diskset.refreshDevices(anaconda.intf, anaconda.id.partitions.reinitializeDisks,
                           anaconda.id.partitions.zeroMbr, anaconda.id.partitions.autoClearPartDrives)

    anaconda.id.diskset.checkNoDisks(anaconda.intf)

    anaconda.id.partitions.setFromDisk(anaconda.id.diskset)
    anaconda.id.partitions.setProtected(anaconda.dispatch)

def partitioningComplete(bl, fsset, diskSet, partitions, intf, instPath, dir):
    if dir == DISPATCH_BACK and fsset.isActive():
        rc = intf.messageWindow(_("Installation cannot continue."),
                                _("The partitioning options you have chosen "
                                  "have already been activated. You can "
                                  "no longer return to the disk editing "
                                  "screen. Would you like to continue "
                                  "with the installation process?"),
                                type = "yesno")
        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    partitions.sortRequests()
    fsset.reset()
    for request in partitions.requests:
        # XXX improve sanity checking
	if (not request.fstype or (request.fstype.isMountable()
	    and not request.mountpoint)):
	    continue
	    
        entry = request.toEntry(partitions)
        if entry:
            fsset.add (entry)
        else:
            raise RuntimeError, ("Managed to not get an entry back from "
                                 "request.toEntry")

    if (not flags.setupFilesystems
        or iutil.memAvailable() > isys.EARLY_SWAP_RAM):
        return
    
    # XXX this attribute is probably going away
    if not partitions.isKickstart:
        rc = intf.messageWindow(_("Low Memory"),
                            _("As you don't have much memory in this "
                              "machine, we need to turn on swap space "
                              "immediately. To do this we'll have to "
                              "write your new partition table to the disk "
                              "immediately. Is that OK?"), "yesno")
    else:
        rc = 1
        
    if rc:
        partitions.doMetaDeletes(diskSet)        
        fsset.setActive(diskSet)
        diskSet.savePartitions ()
        fsset.createLogicalVolumes(instPath)        
        fsset.formatSwap(instPath)
        fsset.turnOnSwap(instPath)

    return



