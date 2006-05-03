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
import math
import isys

from flags import flags
from rhpl.log import log

from constants import *

MAX_LV_SLOTS=256

output = "/tmp/lvmout"

lvmDevicePresent = 0

def has_lvm():
    global lvmDevicePresent

    if not (os.access("/usr/sbin/lvm", os.X_OK) or
            os.access("/sbin/lvm", os.X_OK)):
        return

    if iutil.getArch() == "s390" and not os.access("/proc/devices", os.R_OK):
        return

    f = open("/proc/devices", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        try:
            (dev, name) = line[:-1].split(' ', 2)
        except:
            continue
        if name == "device-mapper":
            lvmDevicePresent = 1
            break
    return lvmDevicePresent
# now check to see if lvm is available
has_lvm()
        

def vgscan():
    """Runs vgscan."""
    global lvmDevicePresent
        
    if flags.test or lvmDevicePresent == 0:
        return

    rc = iutil.execWithRedirect("lvm",
                                ["lvm", "vgscan", "-v"],
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        log("running vgscan failed: %s" %(rc,))
#        lvmDevicePresent = 0

def vgactivate(volgroup = None):
    """Activate volume groups by running vgchange -ay.

    volgroup - optional single volume group to activate
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["lvm", "vgchange", "-ay"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        log("running vgchange failed: %s" %(rc,))
#        lvmDevicePresent = 0

    # now make the device nodes
    args = ["lvm", "vgmknodes"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        log("running vgmknodes failed: %s" %(rc,))
#        lvmDevicePresent = 0

def vgdeactivate(volgroup = None):
    """Deactivate volume groups by running vgchange -an.

    volgroup - optional single volume group to deactivate
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["lvm", "vgchange", "-an"]
    if volgroup:
        args.append(volgroup)
    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        log("running vgchange failed: %s" %(rc,))
#        lvmDevicePresent = 0
    
    
def lvremove(lvname, vgname):
    """Removes a logical volume.

    lvname - name of logical volume to remove.
    vgname - name of volume group lv is in.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["lvm", "lvremove", "-f"]
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
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    # we'll try to deactivate... if it fails, we'll probably fail on
    # the removal too... but it's worth a shot
    try:
        vgdeactivate(vgname)
    except:
        pass

    args = ["lvm", "vgremove", vgname]

    rc = iutil.execWithRedirect(args[0], args,
                                stdout = output,
                                stderr = output,
                                searchPath = 1)
    if rc:
        raise SystemError, "vgremove failed"

def lvlist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    lvs = []
    args = ["lvm", "lvdisplay", "-C", "--noheadings", "--units", "b",
            "--separator", ":", "--nosuffix", "--options",
            "lv_name,vg_name,lv_attr,lv_size"]
    lvscanout = iutil.execWithCapture(args[0], args, searchPath = 1,
                                      stderr = "/dev/tty6")
    for line in lvscanout.split("\n"):
        try:
            (lv, vg, attr, size) = line.strip().split(':')
        except:
            continue
        log("lv is %s/%s, size of %s" %(vg, lv, size))
        lvs.append( (vg, lv, size) )

    return lvs

def pvlist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    pvs = []
    args = ["lvm", "pvdisplay", "-C", "--noheadings", "--units", "b",
            "--separator", ":", "--nosuffix", "--options",
            "pv_name,vg_name,pv_size"]
    scanout = iutil.execWithCapture(args[0], args, searchPath = 1,
                                    stderr = "/dev/tty6")
    for line in scanout.split("\n"):
        try:
            (dev, vg, size) = line.strip().split(':')
        except:
            continue
        log("pv is %s in vg %s, size is %s" %(dev, vg, size))
        pvs.append( (dev, vg, size) )

    return pvs
    
def vglist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    vgs = []
    args = ["lvm", "vgdisplay", "-C", "--noheadings", "--units", "b",
            "--separator", ":", "--nosuffix", "--options",
            "vg_name,vg_size,vg_extent_size"]
    scanout = iutil.execWithCapture(args[0], args, searchPath = 1,
                                    stderr = "/dev/tty6")
    for line in scanout.split("\n"):
        try:
            (vg, size, pesize) = line.strip().split(':')
            pesize = long(pesize)/1024
        except:
            continue
        log("vg %s, size is %s, pesize is %s" %(vg, size, pesize))
        vgs.append( (vg, size, pesize) )

    return vgs

def partialvgs():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []
    
    vgs = []
    args = ["lvm", "vgdisplay", "-C", "--noheadings", "--units", "b", "-P",
            "--separator", ":", "--nosuffix", "--options", "vg_name,vg_attr"]
    scanout = iutil.execWithCapture(args[0], args, searchPath = 1,
                                    stderr = "/dev/tty6")
    for line in scanout.split("\n"):
        try:
            (vg,attr) = line.strip().split(':')
        except:
            continue
        if attr.find("p") != -1:
            log("vg %s, attr is %s" %(vg, attr))
            vgs.append(vg)

    return vgs

# FIXME: this is a hack.  we really need to have a --force option.
def unlinkConf():
    lvmroot = "/etc/lvm"
    if os.path.exists("%s/lvm.conf" %(lvmroot,)):
        os.unlink("%s/lvm.conf" %(lvmroot,))
        
def writeForceConf():
    """Write out an /etc/lvm/lvm.conf that doesn't do much (any?) filtering"""

    lvmroot = "/etc/lvm"
    if not os.path.isdir(lvmroot):
        os.mkdir(lvmroot)

    unlinkConf()

    f = open("%s/lvm.conf" %(lvmroot,), "w+")
    f.write("""
# anaconda hacked lvm.conf to avoid filtering breaking things
devices {
  sysfs_scan = 0
  md_component_detection = 1
}
""")

# FIXME: another hack.  we need to wipe the raid metadata since pvcreate
# doesn't
def wipeOtherMetadataFromPV(node):
    try:
        isys.wipeRaidSB(node)
    except Exception, e:
        log("error wiping raidsb from %s: %s", node, e)
        
    

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

def clampLVSizeRequest(size, pe, roundup=0):
    """Given a size and a PE, returns the actual size of logical volumne.

    size - size (in MB) of logical volume request
    pe   - PE size (in KB)
    roundup - round sizes up or not
    """

    if roundup:
	factor = 1
    else:
	factor = 0
    if ((size*1024L) % pe) == 0:
	return size
    else:
	return ((long((size*1024L)/pe)+factor)*pe)/1024

def clampPVSize(pvsize, pesize):
    """Given a PV size and a PE, returns the usable space of the PV.
    Takes into account both overhead of the physical volume and 'clamping'
    to the PE size.

    pvsize - size (in MB) of PV request
    pesize - PE size (in KB)
    """

    # calculate the number of physical extents.  this is size / pesize
    # with an appropriate factor for kb/mb matchup
    numpes = math.floor(pvsize * 1024 / pesize)

    # now, calculate our "real" overhead.  4 bytes for each PE + 128K
    overhead = (4 * numpes / 1024) + 128

    # now, heuristically, the max of ceil(pesize + 2*overhead) and
    # ceil(2*overhead) is greater than the real overhead, so we won't
    # get people in a situation where they overcommit the vg
    one = math.ceil(pesize + 2 * overhead)
    two = math.ceil(2 * overhead)

    # now we have to do more unit conversion since our overhead in in KB
    if one > two:
        usable = pvsize - math.ceil(one / 1024.0)
    else:
        usable = pvsize - math.ceil(two / 1024.0)

    # finally, clamp to being at a pesize boundary
    return (long(usable*1024/pesize)*pesize)/1024

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
	tmpname = "VolGroup%02d" % (i,)
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
	    
def getVGUsedSpace(vgreq, requests, diskset):
    vgused = 0
    for request in requests.requests:
	if request.type == REQUEST_LV and request.volumeGroup == vgreq.uniqueID:
	    size = int(request.getActualSize(requests, diskset))
	    vgused = vgused + size


    return vgused

def getVGFreeSpace(vgreq, requests, diskset):
    used = getVGUsedSpace(vgreq, requests, diskset)
    
    return vgreq.getActualSize(requests, diskset) - used
