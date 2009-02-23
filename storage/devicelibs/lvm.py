
import os
import math

import iutil

from errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def has_lvm():
    has_lvm = False
    for path in os.environ["PATH"].split(":"):
        if os.access("%s/lvm" % path, os.X_OK):
            has_lvm = True
            break

    if has_lvm:
        has_lvm = False
        for line in open("/proc/devices").readlines():
            if "device-mapper" in line.split():
                has_lvm = True
                break

    return has_lvm

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

def getMaxLVSize(pe):
    """Given a PE size in KB, returns maximum size (in MB) of a logical volume.

    pe - PE size in KB
    """
    if iutil.getArch() in ("x86_64", "ppc64"): #64bit architectures
        return (8*1024*1024*1024*1024) #Max is 8EiB (very large number..)
    else:
        return (16*1024*1024) #Max is 16TiB

def safeLvmName(str):
    tmp = string.strip(str)
    tmp = tmp.replace("/", "_")
    tmp = re.sub("[^0-9a-zA-Z._]", "", str)
    tmp = tmp.lstrip("_")

    return tmp

def getVGUsedSpace(vgreq, requests, diskset):
    vgused = 0
    for request in requests.requests:
	if request.type == REQUEST_LV and request.volumeGroup == vgreq.uniqueID:
	    size = int(request.getActualSize(requests, diskset))
	    vgused = vgused + size


    return vgused

def getVGFreeSpace(vgreq, requests, diskset):
    raise NotImplementedError
    used = getVGUsedSpace(vgreq, requests, diskset)
    log.debug("used space is %s" % (used,))
    
    total = vgreq.getActualSize(requests, diskset)
    log.debug("actual space is %s" % (total,))
    return total - used

def clampSize(size, pesize, roundup=None):
    if roundup:
        round = math.ceil
    else:
        round = math.floor

    return long(round(float(size)/float(pesize)) * pesize)

def pvcreate(device):
    rc = iutil.execWithRedirect("lvm",
                                ["pvcreate", device],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)
    if rc:
        raise LVMError("pvcreate failed for %s" % device)

def pvresize(device, size):
    size_arg = "%dm" % size
    rc = iutil.execWithRedirect("lvm",
                                ["pvresize",
                                 "--setphysicalvolumesize", size_arg,
                                 device],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)
    if rc:
        raise LVMError("pvresize failed for %s" % device)

def pvremove(device):
    rc = iutil.execWithRedirect("lvm",
                                ["pvremove", device],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)
    if rc:
        raise LVMError("pvremove failed for %s" % device)

def pvinfo(device):
    """
        If the PV was created with '--metadacopies 0', lvm will do some
        scanning of devices to determine from their metadata which VG
        this PV belongs to.

        pvs -o pv_name,pv_mda_count,vg_name,vg_uuid --config \
            'devices { scan = "/dev" filter = ["a/loop0/", "r/.*/"] }'
    """
    #cfg = "'devices { scan = \"/dev\" filter = [\"a/%s/\", \"r/.*/\"] }'" 
    rc = iutil.execWithCapture("lvm",
                               ["pvs", "--noheadings",
                                "--units", "m",
                                "-o",
                                "pv_name,pv_mda_count,vg_name,vg_uuid",
                                device],
                                stderr = "/dev/null")
    vals = rc.split()
    if not vals:
        raise LVMError("pvinfo failed for %s" % device)

    info = {'pv_name': vals[0],
            'vg_name': vals[2],
            'vg_uuid': vals[3]}
    return info

def vgcreate(vg_name, pvs, pe_size):
    argv = ["vgcreate"]
    if pe_size:
        argv.extend(["-s", "%dM" % pe_size])
    pv_list = " ".join(pvs)
    argv.append(vg_name)
    argv.append(pv_list)
    rc = iutil.execWithRedirect("lvm",
                                argv,
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("vgcreate failed for %s" % vg_name)

def vgremove(vg_name):
    rc = iutil.execWithRedirect("lvm", ["vgremove", vg_name],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("vgremove failed for %s" % vg_name)

def vgactivate(vg_name):
    rc = iutil.execWithRedirect("lvm", ["vgchange" "-a", "y", vg_name],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)
    if rc:
        raise LVMError("vgactivate failed for %s" % vg_name)

def vgdeactivate(vg_name):
    rc = iutil.execWithRedirect("lvm", ["vgchange", "-a", "n", vg_name],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("vgdeactivate failed for %s" % vg_name)

def vgreduce(vg_name, pv_list):
    pvs = " ".join(pv_list)
    rc = iutil.execWithRedirect("lvm", ["vgreduce", vg_name, pvs],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("vgreduce failed for %s" % vg_name)

def vginfo(vg_name):
    buf = iutil.execWithCapture("lvm",
                ["vgs", "--noheadings", "--nosuffix", "--units", "m", "-o", 
                 "uuid,size,free,extent_size,extent_count,free_count,pv_count",
                 vg_name],
                 stderr="/dev/null")
    info = buf.split()
    if len(info) != 7:
        raise LVMError(_("vginfo failed for %s" % vg_name))

    d = {}
    (d['uuid'],d['size'],d['free'],d['pe_size'],
     d['pe_count'],d['pe_free'],d['pv_count']) = info
    return d

def lvs(vg_name):
    buf = iutil.execWithCapture("lvm",
                                ["lvs", "--noheadings", "--nosuffix",
                                 "--units", "m", "-o",
                                 "lv_name,lv_uuid,lv_size"],
                                stderr="/dev/null")


    lvs = {}
    for line in buf.splitlines():
        line = line.strip()
        if not line:
            continue
        (name, uuid, size) = line.split()
        lvs[name] = {"size": size,
                     "uuid": uuid}
    return lvs

def lvcreate(vg_name, lv_name, size):
    size_arg = "%dm" % size
    rc = iutil.execWithRedirect("lvm",
                                ["lvcreate",
                                 "-L", size_arg,
                                 "-n", lv_name,
                                 vg_name],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("lvcreate failed for %s/%s" % (vg_name, lv_name))

def lvremove(vg_name, lv_name):
    lv_path = "%s/%s" % (vg_name, lv_name)
    rc = iutil.execWithRedirect("lvm", ["lvremove", lv_path],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("lvremove failed for %s" % lv_path)

def lvresize(vg_name, lv_name, size):
    lv_path = "%s/%s" % (vg_name, lv_name)
    size_arg = "%dm" % size
    rc = iutil.execWithRedirect("lvm",
                                ["lvresize",
                                 "-L", size_arg,
                                 lv_path],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("lvresize failed for %s" % lv_path)

def lvactivate(vg_name, lv_name):
    # see if lvchange accepts paths of the form 'mapper/$vg-$lv'
    lv_path = "%s/%s" % (vg_name, lv_name)
    rc = iutil.execWithRedirect("lvm", ["lvchange", "-a", "y", lv_path],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)
    if rc:
        raise LVMError("lvactivate failed for %s" % lv_path)

def lvdeactivate(vg_name, lv_name):
    lv_path = "%s/%s" % (vg_name, lv_name)
    rc = iutil.execWithRedirect("lvm", ["lvchange", "-a", "n", lv_path],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath=1)

    if rc:
        raise LVMError("lvdeactivate failed for %s" % lv_path)



