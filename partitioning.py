#
# partitioning.py: partitioning and other disk management
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
#
# Copyright 2001-2002 Red Hat, Inc.
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
from rhpl.log import log

def get_lvm_volume_group_size(request, requests, diskset):
	# got to add up all of physical volumes to get total size
	if request.physicalVolumes is None:
	    return 0
	totalspace = 0
	for physvolid in request.physicalVolumes:
	    pvreq = requests.getRequestByID(physvolid)
            if pvreq.type != REQUEST_RAID:
                part = partedUtils.get_partition_by_name(diskset.disks,
                                                         pvreq.device)
                partsize = part.geom.length * part.geom.disk.dev.sector_size
            else:
                partsize = get_raid_device_size(pvreq, requests, diskset)

            totalspace = totalspace + partsize

	return totalspace
    

def get_raid_device_size(raidrequest, partitions, diskset):
    if not raidrequest.raidmembers or not raidrequest.raidlevel:
        return 0
    
    raidlevel = raidrequest.raidlevel
    nummembers = len(raidrequest.raidmembers) - raidrequest.raidspares
    smallest = None
    sum = 0
    for member in raidrequest.raidmembers:
        req = partitions.getRequestByID(member)
        device = req.device
        part = partedUtils.get_partition_by_name(diskset.disks, device)
        partsize =  part.geom.length * part.geom.disk.dev.sector_size

        if raid.isRaid0(raidlevel):
            sum = sum + partsize
        else:
            if not smallest:
                smallest = partsize
            elif partsize < smallest:
                smallest = partsize

    if raid.isRaid0(raidlevel):
        return sum
    elif raid.isRaid1(raidlevel):
        return smallest
    elif raid.isRaid5(raidlevel):
        return (nummembers-1) * smallest
    else:
        raise ValueError, "Invalid raidlevel in get_raid_device_size()"

# return the actual size being used by the request in megabytes
def requestSize(req, diskset):
    if req.type == REQUEST_VG:
	if req.size != None:
	    thissize = req.size
	else:
	    thissize = 0
    if req.type == REQUEST_RAID:
        # XXX duplicate the hack below.  
        if req.size != None:
            thissize = req.size
        else:
            thissize = 0
    else:
        part = partedUtils.get_partition_by_name(diskset.disks, req.device)
        if not part:
            # XXX hack for kickstart which ends up calling this
            # before allocating the partitions
            if req.size:
                thissize = req.size
            else:
                thissize = 0
        else:
            thissize = partedUtils.getPartSizeMB(part)
    return thissize





def partitionObjectsInitialize(diskset, partitions, dir, intf):
    if iutil.getArch() == "s390":
        partitions.useAutopartitioning = 0
        partitions.useFdisk = 1
            
    if dir == DISPATCH_BACK:
        diskset.closeDevices()
        return

    # read in drive info
    diskset.refreshDevices(intf, partitions.reinitializeDisks,
                           partitions.zeroMbr)

    diskset.checkNoDisks(intf)

    partitions.setFromDisk(diskset)

def partitionMethodSetup(partitions, dispatch):

    # turn on/off step based on 3 paths:
    #  - use fdisk, then set mount points
    #  - use autopartitioning, then set mount points
    #  - use interactive partitioning tool, continue

    dispatch.skipStep("autopartition",
                      skip = not partitions.useAutopartitioning)
    dispatch.skipStep("autopartitionexecute",
                      skip = not partitions.useAutopartitioning)
    if iutil.getArch() == "s390":
        dispatch.skipStep("fdasd", skip = not partitions.useFdisk)
    else:
        dispatch.skipStep("fdisk", skip = not partitions.useFdisk)

    partitions.setProtected(dispatch)

    
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
        
    if iutil.memInstalled() > isys.EARLY_SWAP_RAM:
        return
    
    # XXX this attribute is probably going away
    if not partitions.isKickstart:
        rc = intf.messageWindow(_("Low Memory"),
                            _("As you don't have much memory in this "
                              "machine, we need to turn on swap space "
                              "immediately. To do this we'll have to "
                              "write your new partition table to the disk "
                              "immediately. Is that OK?"), "okcancel")
    else:
        rc = 0
        
    if rc:
        fsset.setActive(diskSet)
        diskSet.savePartitions ()
        fsset.formatSwap(instPath)
        fsset.turnOnSwap(instPath)

    return



