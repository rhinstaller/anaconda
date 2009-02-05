#
# lvm.py - lvm probing control
#
# Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import iutil
import os,sys
import string
import math
import isys
import re

from flags import flags

import logging
log = logging.getLogger("anaconda")

from constants import *

MAX_LV_SLOTS=256

lvmDevicePresent = 0

from errors import *

def has_lvm():
    global lvmDevicePresent

    if not (os.access("/usr/sbin/lvm", os.X_OK) or
            os.access("/sbin/lvm", os.X_OK)):
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
        
def lvmExec(*args):
    try:
        return iutil.execWithRedirect("lvm", args, stdout = lvmErrorOutput,
            stderr = lvmErrorOutput, searchPath = 1)
    except Exception, e:
        log.error("error running lvm command: %s" %(e,)) 
        raise LvmError, args[0]

def lvmCapture(*args):
    try:
        lvmout = iutil.execWithCapture("lvm", args, stderr = lvmErrorOutput)
        lines = []
        for line in lvmout.split("\n"):
            lines.append(line.strip().split(':'))
        return lines
    except Exception, e:
        log.error("error running lvm command: %s" %(e,))
        raise LvmError, args[0]

def vgscan():
    """Runs vgscan."""
    global lvmDevicePresent
        
    if flags.test or lvmDevicePresent == 0:
        return

    rc = lvmExec("vgscan", "-v")
    if rc:
        log.error("running vgscan failed: %s" %(rc,))
#        lvmDevicePresent = 0

def vgmknodes(volgroup=None):
    # now make the device nodes
    args = ["vgmknodes", "-v"]
    if volgroup:
        args.append(volgroup)
    rc = lvmExec(*args)
    if rc:
        log.error("running vgmknodes failed: %s" %(rc,))
#        lvmDevicePresent = 0

def vgcheckactive(volgroup = None):
    """Check if volume groups are active

    volgroup - optional parameter to inquire about a specific volume group.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return False

    args = ["lvs", "--noheadings", "--units", "b", "--nosuffix",
            "--separator", ":", "--options", "vg_name,lv_name,attr"]
    for line in lvmCapture(*args):
        try:
            (vg, lv, attr) = line
        except:
            continue

        log.info("lv %s/%s, attr is %s" %(vg, lv, attr))
        if attr.find("a") == -1:
            continue

        if volgroup is None or volgroup == vg:
            return True

    return False

def vgactivate(volgroup = None):
    """Activate volume groups by running vgchange -ay.

    volgroup - optional single volume group to activate
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["vgchange", "-ay", "-v"]
    if volgroup:
        args.append(volgroup)
    rc = lvmExec(*args)
    if rc:
        log.error("running vgchange failed: %s" %(rc,))
#        lvmDevicePresent = 0
    vgmknodes(volgroup)

def vgdeactivate(volgroup = None):
    """Deactivate volume groups by running vgchange -an.

    volgroup - optional single volume group to deactivate
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["vgchange", "-an", "-v"]
    if volgroup:
        args.append(volgroup)
    rc = lvmExec(*args)
    if rc:
        log.error("running vgchange failed: %s" %(rc,))
#        lvmDevicePresent = 0

def lvcreate(lvname, vgname, size):
    """Creates a new logical volume.

    lvname - name of logical volume to create.
    vgname - name of volume group lv will be in.
    size - size of lv, in megabytes.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return
    writeForceConf()
    vgscan()

    args = ["lvcreate", "-v", "-L", "%dM" %(size,), "-n", lvname, "-An", vgname]
    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise LVCreateError(vgname, lvname, size)
    unlinkConf()

def lvremove(lvname, vgname):
    """Removes a logical volume.

    lvname - name of logical volume to remove.
    vgname - name of volume group lv is in.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["lvremove", "-f", "-v"]
    dev = "/dev/%s/%s" %(vgname, lvname)
    args.append(dev)

    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise LVRemoveError(vgname, lvname)

def lvresize(lvname, vgname, size):
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    args = ["lvresize", "-An", "-L", "%dM" %(size,), "-v", "--force",
            "/dev/%s/%s" %(vgname, lvname,)]

    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise LVResizeError(vgname, lvname)


def vgcreate(vgname, PESize, nodes):
    """Creates a new volume group."

    vgname - name of volume group to create.
    PESize - Physical Extent size, in kilobytes.
    nodes - LVM Physical Volumes on which to put the new VG.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    # rescan now that we've recreated pvs.  ugh.
    writeForceConf()
    vgscan()

    args = ["vgcreate", "-v", "-An", "-s", "%sk" % (PESize,), vgname ]
    args.extend(nodes)

    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise VGCreateError(vgname, PESize, nodes)
    unlinkConf()

def vgremove(vgname):
    """Removes a volume group.  Deactivates the volume group first

    vgname - name of volume group.
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    # find the Physical Volumes which make up this Volume Group, so we
    # can prune and recreate them.
    pvs = []
    for pv in pvlist():
        if pv[1] == vgname:
            pvs.append(pv[0])

    # we'll try to deactivate... if it fails, we'll probably fail on
    # the removal too... but it's worth a shot
    try:
        vgdeactivate(vgname)
    except:
        pass

    args = ["vgremove", "-v", vgname]

    log.info(string.join(args, ' '))
    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise VGRemoveError, vgname

    # now iterate all the PVs we've just freed up, so we reclaim the metadata
    # space.  This is an LVM bug, AFAICS.
    for pvname in pvs:
        args = ["pvremove", "-ff", "-y", "-v", pvname]

        log.info(string.join(args, ' '))
        try:
            rc = lvmExec(*args)
        except:
            rc = 1
        if rc:
            raise PVRemoveError, pvname

        args = ["pvcreate", "-ff", "-y", "-v", pvname]

        log.info(string.join(args, ' '))
        try:
            rc = lvmExec(*args)
        except:
            rc = 1
        if rc:
            raise PVCreateError, pvname
        wipeOtherMetadataFromPV(pvname)

def pvcreate(node):
    """Initializes a new Physical Volume."

    node - path to device node on which to create the new PV."
    """
    global lvmDevicePresent
    if flags.test or lvmDevicePresent == 0:
        return

    # rescan now that we've recreated pvs.  ugh.
    writeForceConf()

    args = ["pvcreate", "-ff", "-y", "-v", node ]

    try:
        rc = lvmExec(*args)
    except:
        rc = 1
    if rc:
        raise PVCreateError, node
    unlinkConf()
    wipeOtherMetadataFromPV(node)

def lvlist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    lvs = []
    # field names for "options" are in LVM2.2.01.01/lib/report/columns.h
    args = ["lvdisplay", "-C", "--noheadings", "--units", "b",
            "--nosuffix", "--separator", ":", "--options",
            "vg_name,lv_name,lv_size,origin"
           ]
    lvscanout = iutil.execWithCapture("lvm", args, stderr = "/dev/tty6")
    for line in lvmCapture(*args):
        try:
            (vg, lv, size, origin) = line
            size = long(math.floor(long(size) / (1024 * 1024)))
            if origin == '':
                origin = None
        except:
            continue

        logmsg = "lv is %s/%s, size of %s" % (vg, lv, size)
        if origin:
            logmsg += ", snapshot from %s" % (origin,)
        log.info(logmsg)
        lvs.append( (vg, lv, size, origin) )

    return lvs

def pvlist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    pvs = []
    args = ["pvdisplay", "-C", "--noheadings", "--units", "b",
            "--nosuffix", "--separator", ":", "--options",
            "pv_name,vg_name,dev_size"
           ]
    for line in lvmCapture(*args):
        try:
            (dev, vg, size) = line
            size = long(math.floor(long(size) / (1024 * 1024)))
        except:
            continue

        if dev.startswith("/dev/dm-"):
            from block import dm
            try:
                sb = os.stat(dev)
                (major, minor) = (os.major(sb.st_rdev), os.minor(sb.st_rdev))
                for map in dm.maps():
                    if map.dev.major == major and map.dev.minor == minor:
                        dev = "/dev/mapper/%s" % map.name
                        break
            except:
                pass

        log.info("pv is %s in vg %s, size is %s" %(dev, vg, size))
        pvs.append( (dev, vg, size) )

    return pvs
    
def vglist():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []

    vgs = []
    args = ["vgdisplay", "-C", "--noheadings", "--units", "b",
            "--nosuffix", "--separator", ":", "--options",
            "vg_name,vg_size,vg_extent_size,vg_free"
           ]
    for line in lvmCapture(*args):
        try:
            (vg, size, pesize, free) = line
            size = long(math.floor(long(size) / (1024 * 1024)))
            pesize = long(pesize)/1024
            free = math.floor(long(free) / (1024 * 1024))
        except:
            continue
        log.info("vg %s, size is %s, pesize is %s" %(vg, size, pesize))
        vgs.append( (vg, size, pesize, free) )
    return vgs

def partialvgs():
    global lvmDevicePresent
    if lvmDevicePresent == 0:
        return []
    
    vgs = []
    args = ["vgdisplay", "-C", "-P", "--noheadings", "--units", "b",
            "--nosuffix", "--separator", ":"]
    for line in lvmCapture(*args):
        try:
            (vg, numpv, numlv, numsn, attr, size, free) = line
        except:
            continue
        if attr.find("p") != -1:
            log.info("vg %s, attr is %s" %(vg, attr))
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
    try:
        os.unlink("/etc/lvm/.cache")
    except:
        pass
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
        log.critical("error wiping raidsb from %s: %s", node, e)
        
    

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
        func = math.ceil
    else:
        func = math.floor
    return (long(func((size*1024L)/pe))*pe)/1024

def clampPVSize(pvsize, pesize):
    """Given a PV size and a PE, returns the usable space of the PV.
    Takes into account both overhead of the physical volume and 'clamping'
    to the PE size.

    pvsize - size (in MB) of PV request
    pesize - PE size (in KB)
    """

    # we want Kbytes as a float for our math
    pvsize *= 1024.0
    return long((math.floor(pvsize / pesize) * pesize) / 1024)

def getMaxLVSize(pe):
    """Given a PE size in KB, returns maximum size (in MB) of a logical volume.

    pe - PE size in KB
    """

    if os.uname()[2][:4]=="2.4.":
        return pe*64 #2.4 kernel - LVM1, max size is 2TiB and depends on extent size/count

    else: #newer kernel - LVM2, size limited by number of sectors
        if productArch in ("x86_64", "ppc64"): #64bit architectures
            return (8*1024*1024*1024*1024) #Max is 8EiB (very large number..)
        else:
            return (16*1024*1024) #Max is 16TiB

def safeLvmName(str):
    tmp = string.strip(str)
    tmp = tmp.replace("/", "_")
    tmp = re.sub("[^0-9a-zA-Z._]", "", str)
    tmp = tmp.lstrip("_")

    return tmp

def createSuggestedVGName(partitions, network):
    """Given list of partition requests, come up with a reasonable VG name

    partitions - list of requests
    """

    # try to create a volume group name incorporating the hostname
    hn = network.hostname
    if hn is not None and hn != '':
        if hn == 'localhost' or hn == 'localhost.localdomain':
            vgtemplate = "VolGroup"
        elif hn.find('.') != -1:
            hn = safeLvmName(hn)
            vgtemplate = "vg_%s" % (hn.split('.')[0].lower(),)
        else:
            hn = safeLvmName(hn)
            vgtemplate = "vg_%s" % (hn.lower(),)
    else:
        vgtemplate = "VolGroup"

    if not partitions.isVolumeGroupNameInUse(vgtemplate):
        return vgtemplate
    else:
        i = 0
        while 1:
            tmpname = "%s%02d" % (vgtemplate, i,)
            if not partitions.isVolumeGroupNameInUse(tmpname):
                break

            i += 1
            if i > 99:
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

        i += 1
        if i > 99:
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
    log.debug("used space is %s" % (used,))
    
    total = vgreq.getActualSize(requests, diskset)
    log.debug("actual space is %s" % (total,))
    return total - used
