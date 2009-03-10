#
# lvm.py
# lvm functions
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
# Author(s): Dave Lehman <dlehman@redhat.com>
#

import os
import math
import re

import iutil

from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

MAX_LV_SLOTS = 256

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

# Start config_args handling code
#
# Theoretically we can handle all that can be handled with the LVM --config
# argument.  For every time we call an lvm_cc (lvm compose config) funciton
# we regenerate the config_args with all global info.
config_args = [] # Holds the final argument list
config_args_data = { "filterRejects": [],    # regular expressions to reject.
                            "filterAccepts": [] }   # regexp to accept

def _composeConfig():
    """lvm command accepts lvm.conf type arguments preceded by --config. """
    global config_args, config_args_data
    config_args = []

    filter_string = ""
    rejects = config_args_data["filterRejects"]
    # we don't need the accept for now.
    # accepts = config_args_data["filterAccepts"]
    # if len(accepts) > 0:
    #   for i in range(len(rejects)):
    #       filter_string = filter_string + ("\"a|%s|\", " % accpets[i])

    if len(rejects) > 0:
        for i in range(len(rejects)):
            filter_string = filter_string + ("\"r|%s|\", " % rejects[i])


    filter_string = " filter=[%s] " % filter_string.strip(",")

    # As we add config strings we should check them all.
    if filter_string == "":
        # Nothing was really done.
        return

    # devices_string can have (inside the brackets) "dir", "scan",
    # "preferred_names", "filter", "cache_dir", "write_cache_state",
    # "types", "sysfs_scan", "md_component_detection".  see man lvm.conf.
    devices_string = " devices { %s } " % (filter_string) # strings can be added
    config_string = devices_string # more strings can be added.
    config_args = ["--config", config_string]

def lvm_cc_addFilterRejectRegexp(regexp):
    """ Add a regular expression to the --config string."""
    global config_args_data
    config_args_data["filterRejects"].append(regexp)

    # compoes config once more.
    _composeConfig()
# End config_args handling code.

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

def getMaxLVSize():
    """ Return the maximum size (in MB) of a logical volume. """
    if iutil.getArch() in ("x86_64", "ppc64"): #64bit architectures
        return (8*1024*1024*1024*1024) #Max is 8EiB (very large number..)
    else:
        return (16*1024*1024) #Max is 16TiB

def safeLvmName(name):
    tmp = name.strip()
    tmp = tmp.replace("/", "_")
    tmp = re.sub("[^0-9a-zA-Z._]", "", tmp)
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
    args = ["pvcreate"] + \
            config_args + \
            [device]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)
    if rc:
        raise LVMError("pvcreate failed for %s" % device)

def pvresize(device, size):
    args = ["pvresize"] + \
            ["--setphysicalvolumesize", ("%dm" % size)] + \
            config_args + \
            [device]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)
    if rc:
        raise LVMError("pvresize failed for %s" % device)

def pvremove(device):
    args = ["pvremove"] + \
            config_args + \
            [device]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
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
    args = ["pvs", "--noheadings"] + \
            ["--units", "m"] + \
            ["-o", "pv_name,pv_mda_count,vg_name,vg_uuid"] + \
            config_args + \
            [device]

    rc = iutil.execWithCapture("lvm", args,
                                stderr = "/dev/tty5")
    vals = rc.split()
    if not vals:
        raise LVMError("pvinfo failed for %s" % device)

    # don't raise an exception if pv is not a part of any vg
    pv_name = vals[0]
    try:
        vg_name, vg_uuid = vals[2], vals[3]
    except IndexError:
        vg_name, vg_uuid = "", ""
    
    info = {'pv_name': pv_name,
            'vg_name': vg_name,
            'vg_uuid': vg_uuid}

    return info

def vgcreate(vg_name, pv_list, pe_size):
    argv = ["vgcreate"]
    if pe_size:
        argv.extend(["-s", "%dM" % pe_size])
    argv.extend(config_args)
    argv.append(vg_name)
    argv.extend(pv_list)

    rc = iutil.execWithRedirect("lvm", argv,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("vgcreate failed for %s" % vg_name)

def vgremove(vg_name):
    args = ["vgremove"] + \
            config_args +\
            [vg_name]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("vgremove failed for %s" % vg_name)

def vgactivate(vg_name):
    args = ["vgchange", "-a", "y"] + \
            config_args + \
            [vg_name]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)
    if rc:
        raise LVMError("vgactivate failed for %s" % vg_name)

def vgdeactivate(vg_name):
    args = ["vgchange", "-a", "n"] + \
            config_args + \
            [vg_name]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("vgdeactivate failed for %s" % vg_name)

def vgreduce(vg_name, pv_list):
    args = ["vgreduce"] + \
            config_args + \
            [vg_name] + \
            pv_list

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("vgreduce failed for %s" % vg_name)

def vginfo(vg_name):
    args = ["vgs", "--noheadings", "--nosuffix"] + \
            ["--units", "m"] + \
            ["-o", "uuid,size,free,extent_size,extent_count,free_count,pv_count"] + \
            config_args + \
            [vg_name]

    buf = iutil.execWithCapture("lvm",
                                args,
                                stderr="/dev/tty5")
    info = buf.split()
    if len(info) != 7:
        raise LVMError(_("vginfo failed for %s" % vg_name))

    d = {}
    (d['uuid'],d['size'],d['free'],d['pe_size'],
     d['pe_count'],d['pe_free'],d['pv_count']) = info
    return d

def lvs(vg_name):
    args = ["lvs", "--noheadings", "--nosuffix"] + \
            ["--units", "m"] + \
            ["-o", "lv_name,lv_uuid,lv_size"] + \
            config_args + \
            [vg_name]

    buf = iutil.execWithCapture("lvm",
                                args,
                                stderr="/dev/tty5")

    lvs = {}
    for line in buf.splitlines():
        line = line.strip()
        if not line:
            continue
        (name, uuid, size) = line.split()
        lvs[name] = {"size": size,
                     "uuid": uuid}

    if not lvs:
        raise LVMError(_("lvs failed for %s" % vg_name))

    return lvs

def lvcreate(vg_name, lv_name, size):
    args = ["lvcreate"] + \
            ["-L", "%dm" % size] + \
            ["-n", lv_name] + \
            config_args + \
            [vg_name]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("lvcreate failed for %s/%s" % (vg_name, lv_name))

def lvremove(vg_name, lv_name):
    args = ["lvremove"] + \
            config_args + \
            ["%s/%s" % (vg_name, lv_name)]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("lvremove failed for %s" % lv_path)

def lvresize(vg_name, lv_name, size):
    args = ["lvresize"] + \
            ["-L", "%dm" % size] + \
            config_args + \
            ["%s/%s" % (vg_name, lv_name)]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("lvresize failed for %s" % lv_path)

def lvactivate(vg_name, lv_name):
    # see if lvchange accepts paths of the form 'mapper/$vg-$lv'
    args = ["lvchange", "-a", "y"] + \
            config_args + \
            ["%s/%s" % (vg_name, lv_name)]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)
    if rc:
        raise LVMError("lvactivate failed for %s" % lv_path)

def lvdeactivate(vg_name, lv_name):
    args = ["lvchange", "-a", "n"] + \
            config_args + \
            ["%s/%s" % (vg_name, lv_name)]

    rc = iutil.execWithRedirect("lvm", args,
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise LVMError("lvdeactivate failed for %s" % lv_path)

