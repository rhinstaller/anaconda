# lvm.py - lvm probing control
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import iutil
import os,sys
import string

output = "/tmp/lvmout"

def vgscan():
    """Runs vgscan."""

    rc = iutil.execWithRedirect("vgscan",
                                ["vgscan", "-v"],
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgscan failed"

def vgactivate(volgroup = None):
    """Activate volume groups by running vgchange -ay.

    volgroup - optional single volume group to activate
    """

    args = ["vgchange", "-ay", "-An"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgchange failed"

def vgdeactivate(volgroup = None):
    """Deactivate volume groups by running vgchange -an.

    volgroup - optional single volume group to deactivate
    """

    args = ["vgchange", "-an", "-An"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgchange failed"
    
    
def lvremove(lvname, vgname):
    """Removes a logical volume.

    lvname - name of logical volume to remove.
    vgname - name of volume group lv is in.
    """

    args = ["lvremove", "-f", "-An"]
    dev = "/dev/%s/%s" %(vgname, lvname)
    args.append(dev)

    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "lvremove failed"


def vgremove(vgname):
    """Removes a volume group.  Deactivates the volume group first

    vgname - name of volume group.
    """

    # we'll try to deactivate... if it fails, we'll probably fail on
    # the removal too... but it's worth a shot
    try:
        vgdeactivate(vgname)
    except:
        pass

    args = ["vgremove", vgname]

    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgremove failed"

def getPossiblePhysicalExtents(floor=0):
    """Returns a list of integers representing the possible values for
       the physical extent of a volume group.  Value is in KB.

       floor - size (in KB) of smallest PE we care about.
    """

    possiblePE = []
    curpe = 8
    while curpe <= 16384*1024:
	if curpe >= floor:
	    possiblePE.append(curpe)
	curpe = curpe * 2

    return possiblePE

def clampLVSizeRequest(size, pe):
    """Given a size and a PE, returns the actual size of logical volumne.

    size - size (in MB) of logical volume request
    pe   - PE size (in KB)
    """

    if ((size*1024L) % pe) == 0:
	return size
    else:
	return ((long((size*1024L)/pe)+1L)*pe)/1024

def clampPVSize(pvsize, pesize):
    """Given a PV size and a PE, returns the usable space of the PV.

    pvsize - size (in MB) of PV request
    pesize - PE size (in KB)
    """

    return (long(pvsize*1024/pesize)*pesize)/1024
    
def getMaxLVSize(pe):
    """Given a PE size in KB, returns maximum size (in MB) of a logical volume.

    pe - PE size in KB
    """
    return pe*64

def createSuggestedVGName(partitions):
    """Given list of partition requests, come up with a reasonable VG name

    partitions - list of requests
    """
    i = 0
    while 1:
	tmpname = "Volume%02d" % (i,)
	if not partitions.isVolumeGroupNameInUse(tmpname):
	    break

	i = i + 1
	if i>99:
	    tmpname = ""

    return tmpname
	    
def createSuggestedLVName(logreqs):
    """Given list of LV requests, come up with a reasonable LV name

    partitions - list of LV requests for this VG
    """
    i = 0

    lnames = []
    for lv in logreqs:
	lnames.append(lv.logicalVolumeName)
    
    while 1:
	tmpname = "LogVol%02d" % (i,)
	if (logreqs is None) or (tmpname not in lnames):
	    break

	i = i + 1
	if i>99:
	    tmpname = ""

    return tmpname
	    
