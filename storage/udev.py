# udev.py
# Python module for querying the udev database for device information.
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

import os
import re

import iutil
from errors import *

import logging
log = logging.getLogger("storage")


def udev_get_block_devices():
    udev_settle(timeout=2)
    entries = []
    for path in enumerate_block_devices():
        entry = udev_get_block_device(path)
        if entry:
            entries.append(entry)
    return entries

def __is_blacklisted_blockdev(dev_name):
    """Is this a blockdev we never want for an install?"""
    if dev_name.startswith("loop") or dev_name.startswith("ram"):
        return True

    return False

def enumerate_block_devices():
    top_dir = "/sys/class/block"
    devices = []
    for dev_name in os.listdir(top_dir):
        if __is_blacklisted_blockdev(dev_name):
            continue
        full_path = os.path.join(top_dir, dev_name)
        link_ref = os.readlink(full_path)
        real_path = os.path.join(top_dir, link_ref)
        sysfs_path = os.path.normpath(real_path)
        devices.append(sysfs_path)
    return devices

def udev_get_block_device(sysfs_path):
    if not os.path.exists(sysfs_path):
        log.debug("%s does not exist" % sysfs_path)
        return None

    db_entry = sysfs_path[4:].replace("/", "\\x2f")
    db_root = "/dev/.udev/db"
    db_path = os.path.normpath("%s/%s" % (db_root, db_entry))
    if not os.access(db_path, os.R_OK):
        log.debug("db entry %s does not exist" % db_path)
        return None

    entry = open(db_path).read()
    dev = udev_parse_block_entry(entry)
    if dev:
        # XXX why do we do this? is /sys going to move during installation?
        dev['sysfs_path'] = sysfs_path[4:]  # strip off the leading '/sys'
        dev = udev_parse_uevent_file(dev)

    # now add in the contents of the uevent file since they're handy
    return dev

def udev_parse_uevent_file(dev):
    path = os.path.normpath("/sys/%s/uevent" % dev['sysfs_path'])
    if not os.access(path, os.R_OK):
        return dev

    with open(path) as f:
        for line in f.readlines():
            (key, equals, value) = line.strip().partition("=")
            if not equals:
                continue

            dev[key] = value

    return dev

def udev_parse_block_entry(buf):
    dev = {'name': None,
           'symlinks': []}

    for line in buf.splitlines():
        line.strip()
        (tag, sep, val) = line.partition(":")
        if not sep:
            continue

        if tag == "N":
            dev['name'] = val
        elif tag == "S":
            dev['symlinks'].append(val)
        elif tag == "E":
            if val.count("=") > 1 and val.count(" ") > 0:
                # eg: LVM2_LV_NAME when querying the VG for its LVs
                vars = val.split()
                vals = []
                var_name = None
                for (index, subval) in enumerate(vars):
                    (var_name, sep, var_val) = subval.partition("=")
                    if sep:
                        vals.append(var_val)

                dev[var_name] = vals
            else:
                (var_name, sep, var_val) = val.partition("=")
                if not sep:
                    continue

                if var_val.count(" "):
                    # eg: DEVLINKS
                    var_val = var_val.split()

                dev[var_name] = var_val

    if dev.get("name"):
        return dev

def udev_settle(timeout=None):
    argv = ["settle"]
    if timeout:
        argv.append("--timeout=%d" % int(timeout))

    iutil.execWithRedirect("udevadm", argv, stderr="/dev/null", searchPath=1)

def udev_trigger(subsystem=None):
    argv = ["trigger"]
    if subsystem:
        argv.append("--subsystem-match=%s" % subsystem)

    iutil.execWithRedirect("udevadm", argv, stderr="/dev/null", searchPath=1)


""" These are functions for retrieving specific pieces of information from
    udev database entries.
"""
def udev_device_get_name(udev_info):
    """ Return the best name for a device based on the udev db data. """
    return udev_info.get("DM_NAME", udev_info["name"])

def udev_device_get_format(udev_info):
    """ Return a device's format type as reported by udev. """
    return udev_info.get("ID_FS_TYPE")

def udev_device_get_uuid(udev_info):
    """ Get the UUID from the device's format as reported by udev. """
    md_uuid = udev_info.get("MD_UUID")
    uuid = udev_info.get("ID_FS_UUID")
    # we don't want to return the array's uuid as a member's uuid
    if uuid and not md_uuid == uuid:
        return udev_info.get("ID_FS_UUID")

def udev_device_get_label(udev_info):
    """ Get the label from the device's format as reported by udev. """
    return udev_info.get("ID_FS_LABEL")

def udev_device_is_dm(info):
    """ Return True if the device is a device-mapper device. """
    return info.has_key("DM_NAME")

def udev_device_is_md(info):
    """ Return True is the device is an mdraid array device. """
    return info.has_key("MD_METADATA")

def udev_device_is_cdrom(info):
    """ Return True if the device is an optical drive. """
    # FIXME: how can we differentiate USB drives from CD-ROM drives?
    #         -- USB drives also generate a sdX device.
    return info.get("ID_CDROM") == "1"

def udev_device_is_disk(info):
    """ Return True is the device is a disk. """
    has_range = os.path.exists("/sys/%s/range" % info['sysfs_path'])
    return info.get("DEVTYPE") == "disk" or has_range

def udev_device_is_partition(info):
    has_start = os.path.exists("/sys/%s/start" % info['sysfs_path'])
    return info.get("DEVTYPE") == "partition" or has_start

def udev_device_get_sysfs_path(info):
    return info['sysfs_path']

def udev_device_get_major(info):
    return int(info["MAJOR"])

def udev_device_get_minor(info):
    return int(info["MINOR"])

def udev_device_get_md_level(info):
    return info["MD_LEVEL"]

def udev_device_get_md_devices(info):
    return int(info["MD_DEVICES"])

def udev_device_get_md_uuid(info):
    return info["MD_UUID"]

def udev_device_get_vg_name(info):
    return info['LVM2_VG_NAME']

def udev_device_get_vg_uuid(info):
    return info['LVM2_VG_UUID']

def udev_device_get_vg_size(info):
    # lvm's decmial precision is not configurable, so we tell it to use
    # KB and convert to MB here
    return float(info['LVM2_VG_SIZE']) / 1024

def udev_device_get_vg_free(info):
    # lvm's decmial precision is not configurable, so we tell it to use
    # KB and convert to MB here
    return float(info['LVM2_VG_FREE']) / 1024

def udev_device_get_vg_extent_size(info):
    # lvm's decmial precision is not configurable, so we tell it to use
    # KB and convert to MB here
    return float(info['LVM2_VG_EXTENT_SIZE']) / 1024

def udev_device_get_vg_extent_count(info):
    return int(info['LVM2_VG_EXTENT_COUNT'])

def udev_device_get_vg_free_extents(info):
    return int(info['LVM2_VG_FREE_COUNT'])

def udev_device_get_vg_pv_count(info):
    return int(info['LVM2_PV_COUNT'])

def udev_device_get_pv_pe_start(info):
    # lvm's decmial precision is not configurable, so we tell it to use
    # KB and convert to MB here
    return float(info['LVM2_PE_START']) / 1024

def udev_device_get_lv_names(info):
    names = info['LVM2_LV_NAME']
    if not names:
        names = []
    elif not isinstance(names, list):
        names = [names]
    return names

def udev_device_get_lv_uuids(info):
    uuids = info['LVM2_LV_UUID']
    if not uuids:
        uuids = []
    elif not isinstance(uuids, list):
        uuids = [uuids]
    return uuids

def udev_device_get_lv_sizes(info):
    # lvm's decmial precision is not configurable, so we tell it to use
    # KB and convert to MB here
    sizes = info['LVM2_LV_SIZE']
    if not sizes:
        sizes = []
    elif not isinstance(sizes, list):
        sizes = [sizes]

    return [float(s) / 1024 for s in sizes]

def udev_device_is_dmraid(info):
    # Note that this function does *not* identify raid sets.
    # Tests to see if device is parto of a dmraid set.
    # dmraid and mdriad have the same ID_FS_USAGE string,  ID_FS_TYPE has a
    # string that describes the type of dmraid (isw_raid_member...),  I don't
    # want to maintain a list and mdraid's ID_FS_TYPE='linux_raid_member', so
    # dmraid will be everything that is raid and not linux_raid_member
    from formats.dmraid import DMRaidMember
    if info.has_key("ID_FS_TYPE") and \
            info["ID_FS_TYPE"] in DMRaidMember._udevTypes:
        return True

    return False

def udev_device_get_dmraid_partition_disk(info):
    try:
        p_index = info["DM_NAME"].rindex("p")
    except:
        return None

    if not info["DM_NAME"][p_index+1:].isdigit():
        return None

    return info["DM_NAME"][:p_index]

def udev_device_is_dmraid_partition(info, devicetree):
    diskname = udev_device_get_dmraid_partition_disk(info)
    dmraid_devices = devicetree.getDevicesByType("dm-raid array")

    for device in dmraid_devices:
        if diskname == device.name:
            return True

    return False

# iscsi disks have ID_PATH in the form of:
# ip-${iscsi_address}:${iscsi_port}-iscsi-${iscsi_tgtname}-lun-${lun}
def udev_device_is_iscsi(info):
    try:
        path_components = info["ID_PATH"].split("-")

        if info["ID_BUS"] == "scsi" and len(path_components) >= 6 and \
           path_components[0] == "ip" and path_components[2] == "iscsi":
            return True
    except KeyError:
        pass

    return False

def udev_device_get_iscsi_name(info):
    path_components = info["ID_PATH"].split("-")

    # Tricky, the name itself contains atleast 1 - char
    return "-".join(path_components[3:len(path_components)-2])

def udev_device_get_iscsi_address(info):
    path_components = info["ID_PATH"].split("-")

    return path_components[1].split(":")[0]

def udev_device_get_iscsi_port(info):
    path_components = info["ID_PATH"].split("-")

    return path_components[1].split(":")[1]
