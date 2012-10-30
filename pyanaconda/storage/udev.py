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

from pyanaconda import iutil
from errors import *
from pyanaconda.baseudev import *

import logging
log = logging.getLogger("storage")

def udev_resolve_devspec(devspec):
    if not devspec:
        return None

    import devices as _devices
    ret = None
    for dev in udev_get_block_devices():
        if devspec.startswith("LABEL="):
            if udev_device_get_label(dev) == devspec[6:]:
                ret = dev
                break
        elif devspec.startswith("UUID="):
            if udev_device_get_uuid(dev) == devspec[5:]:
                ret = dev
                break
        elif udev_device_get_name(dev) == _devices.devicePathToName(devspec):
            ret = dev
            break
        else:
            spec = devspec
            if not spec.startswith("/dev/"):
                spec = os.path.normpath("/dev/" + spec)

            for link in dev["symlinks"]:
                if spec == link:
                    ret = dev
                    break

    del _devices
    if ret:
        return udev_device_get_name(ret)

def udev_resolve_glob(glob):
    import fnmatch
    ret = []

    if not glob:
        return ret

    for dev in udev_get_block_devices():
        name = udev_device_get_name(dev)

        if fnmatch.fnmatch(name, glob):
            ret.append(name)
        else:
            for link in dev["symlinks"]:
                if fnmatch.fnmatch(link, glob):
                    ret.append(name)

    return ret

def udev_get_block_devices():
    udev_settle()
    entries = []
    for path in udev_enumerate_block_devices():
        entry = udev_get_block_device(path)
        if entry:
            if entry["name"].startswith("md"):
                # mdraid is really braindead, when a device is stopped
                # it is no longer usefull in anyway (and we should not
                # probe it) yet it still sticks around, see bug rh523387
                state = None
                state_file = "/sys/%s/md/array_state" % entry["sysfs_path"]
                if os.access(state_file, os.R_OK):
                    state = open(state_file).read().strip()
                if state == "clear":
                    continue
            entries.append(entry)
    return entries

def __is_blacklisted_blockdev(dev_name):
    """Is this a blockdev we never want for an install?"""
    if dev_name.startswith("ram") or dev_name.startswith("fd"):
        return True

    if os.path.exists("/sys/class/block/%s/device/model" %(dev_name,)):
        model = open("/sys/class/block/%s/device/model" %(dev_name,)).read()
        for bad in ("IBM *STMF KERNEL", "SCEI Flash-5", "DGC LUNZ"):
            if model.find(bad) != -1:
                log.info("ignoring %s with model %s" %(dev_name, model))
                return True

    return False

def udev_enumerate_block_devices():
    import os.path

    return filter(lambda d: not __is_blacklisted_blockdev(os.path.basename(d)),
                  udev_enumerate_devices(deviceClass="block"))

def udev_get_block_device(sysfs_path):
    dev = udev_get_device(sysfs_path)
    if not dev or not dev.has_key("name"):
        return None
    else:
        return dev


# These are functions for retrieving specific pieces of information from
# udev database entries.
def udev_device_get_name(udev_info):
    """ Return the best name for a device based on the udev db data. """
    if "DM_NAME" in udev_info:
        name = udev_info["DM_NAME"]
    else:
        name = udev_info["name"]

    return name

def udev_device_get_format(udev_info):
    """ Return a device's format type as reported by udev. """
    return udev_info.get("ID_FS_TYPE")

def udev_device_get_uuid(udev_info):
    """ Get the UUID from the device's format as reported by udev. """
    md_uuid = udev_info.get("MD_UUID", '')
    uuid = udev_info.get("ID_FS_UUID", '')
    # we don't want to return the array's uuid as a member's uuid
    if len(uuid) > 0 and \
            re.sub(r'\W', '', md_uuid) != re.sub(r'\W', '', uuid):
        return udev_info.get("ID_FS_UUID")

def udev_device_get_label(udev_info):
    """ Get the label from the device's format as reported by udev. """
    return udev_info.get("ID_FS_LABEL")

def udev_device_is_dm(info):
    """ Return True if the device is a device-mapper device. """
    return info.has_key("DM_NAME")

def udev_device_is_md(info):
    """ Return True if the device is a mdraid array device. """
    # Don't identify partitions on mdraid arrays as raid arrays
    if udev_device_is_partition(info):
        return False

    # The udev information keeps shifting around. Only md arrays have a
    # /sys/class/block/<name>/md/ subdirectory.
    md_dir = "/sys" + udev_device_get_sysfs_path(info) + "/md"
    return os.path.exists(md_dir)

def udev_device_is_cciss(info):
    """ Return True if the device is a CCISS device. """
    return udev_device_get_name(info).startswith("cciss")

def udev_device_is_dasd(info):
    """ Return True if the device is a dasd device. """
    devname = info.get("DEVNAME")
    if devname:
        return devname.startswith("dasd")
    else:
        return False

def udev_device_is_zfcp(info):
    """ Return True if the device is a zfcp device. """
    if info.get("DEVTYPE") != "disk":
        return False

    subsystem = "/sys" + info.get("sysfs_path")

    while True:
        topdir = os.path.realpath(os.path.dirname(subsystem))
        driver = "%s/driver" % (topdir,)

        if os.path.islink(driver):
            subsystemname = os.path.basename(os.readlink(subsystem))
            drivername = os.path.basename(os.readlink(driver))

            if subsystemname == 'ccw' and drivername == 'zfcp':
                return True

        newsubsystem = os.path.dirname(topdir)

        if newsubsystem == topdir:
            break

        subsystem = newsubsystem + "/subsystem"

    return False

def udev_device_get_zfcp_attribute(info, attr=None):
    """ Return the value of the specified attribute of the zfcp device. """
    if not attr:
        log.debug("udev_device_get_zfcp_attribute() called with attr=None")
        return None

    attribute = "/sys%s/device/%s" % (info.get("sysfs_path"), attr,)
    attribute = os.path.realpath(attribute)

    if not os.path.isfile(attribute):
        log.warning("%s is not a valid zfcp attribute" % (attribute,))
        return None

    return open(attribute, "r").read().strip()

def udev_device_get_dasd_bus_id(info):
    """ Return the CCW bus ID of the dasd device. """
    return info.get("sysfs_path").split("/")[-3]

def udev_device_get_dasd_flag(info, flag=None):
    """ Return the specified flag for the dasd device. """
    if flag is None:
        return None

    path = "/sys" + info.get("sysfs_path") + "/device/" + flag
    if not os.path.isfile(path):
        return None

    return open(path, 'r').read().strip()

def udev_device_is_cdrom(info):
    """ Return True if the device is an optical drive. """
    # FIXME: how can we differentiate USB drives from CD-ROM drives?
    #         -- USB drives also generate a sdX device.
    return info.get("ID_CDROM") == "1"

def udev_device_is_disk(info):
    """ Return True is the device is a disk. """
    if udev_device_is_cdrom(info):
        return False
    has_range = os.path.exists("/sys/%s/range" % info['sysfs_path'])
    return info.get("DEVTYPE") == "disk" or has_range

def udev_device_is_partition(info):
    has_start = os.path.exists("/sys/%s/start" % info['sysfs_path'])
    return info.get("DEVTYPE") == "partition" or has_start

def udev_device_is_loop(info):
    """ Return True if the device is a configured loop device. """
    return (udev_device_get_name(info).startswith("loop") and
            os.path.isdir("/sys/%s/loop" % info['sysfs_path']))

def udev_device_get_serial(udev_info):
    """ Get the serial number/UUID from the device as reported by udev. """
    return udev_info.get("ID_SERIAL_RAW", udev_info.get("ID_SERIAL_SHORT", udev_info.get("ID_SERIAL")))

def udev_device_get_wwid(udev_info):
    """ The WWID of a device is typically just its serial number, but with
        colons in the name to make it more readable. """
    serial = udev_device_get_serial(udev_info)
    return iutil.insert_colons(serial) if serial else ""

def udev_device_get_vendor(udev_info):
    """ Get the vendor of the device as reported by udev. """
    return udev_info.get("ID_VENDOR_FROM_DATABASE", udev_info.get("ID_VENDOR"))

def udev_device_get_model(udev_info):
    """ Get the model of the device as reported by udev. """
    return udev_info.get("ID_MODEL_FROM_DATABASE", udev_info.get("ID_MODEL"))

def udev_device_get_bus(udev_info):
    """ Get the bus a device is connected to the system by. """
    return udev_info.get("ID_BUS", "").upper()

def udev_device_get_path(info):
    return info["ID_PATH"]

def udev_device_get_by_path(info):
    if info.has_key('symlinks'):
        for link in info['symlinks']:
            if link.startswith('/dev/disk/by-path/'):
                return link

    return udev_device_get_name(info)

def udev_device_get_sysfs_path(info):
    return info['sysfs_path']

def udev_device_get_major(info):
    return int(info["MAJOR"])

def udev_device_get_minor(info):
    return int(info["MINOR"])

def udev_device_get_md_level(info):
    return info.get("MD_LEVEL")

def udev_device_get_md_devices(info):
    return int(info["MD_DEVICES"])

def udev_device_get_md_uuid(info):
    return info["MD_UUID"]

def udev_device_get_md_container(info):
    return info.get("MD_CONTAINER")

def udev_device_get_md_name(info):
    return info.get("MD_DEVNAME")

def udev_device_get_vg_name(info):
    return info['LVM2_VG_NAME']

def udev_device_get_lv_vg_name(info):
    return info['DM_VG_NAME']

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

def udev_device_get_lv_attr(info):
    attr = info['LVM2_LV_ATTR']
    if not attr:
        attr = []
    elif not isinstance(attr, list):
        attr = [attr]
    return attr

def udev_device_dm_subsystem_match(info, subsystem):
    """ Return True if the device matches a given device-mapper subsystem. """
    uuid = info.get("DM_UUID", "")
    uuid_fields = uuid.split("-")
    _subsystem = uuid_fields[0]
    if _subsystem.lower().startswith("part") and len(uuid_fields) > 1:
        # kpartx uses partN- as a subsystem prefix, which we ignore because
        # we only care about the subsystem of the partitions' parent device.
        _subsystem = uuid_fields[1]

    if _subsystem == uuid or not _subsystem:
        return False

    return _subsystem.lower() == subsystem.lower()

def udev_device_is_dm_lvm(info):
    """ Return True if the device is an LVM logical volume. """
    return udev_device_dm_subsystem_match(info, "lvm")

def udev_device_is_dm_crypt(info):
    """ Return True if the device is a mapped dm-crypt device. """
    return udev_device_dm_subsystem_match(info, "crypt")

def udev_device_is_dm_luks(info):
    """ Return True if the device is a mapped LUKS device. """
    is_crypt = udev_device_dm_subsystem_match(info, "crypt")
    try:
        _type = info.get("DM_UUID", "").split("-")[1].lower()
    except IndexError:
        _type = ""

    return is_crypt and _type.startswith("luks")

def udev_device_is_dm_raid(info):
    """ Return True if the device is a dmraid array device. """
    return udev_device_dm_subsystem_match(info, "dmraid")

def udev_device_is_dm_mpath(info):
    """ Return True if the device is a multipath device. """
    return udev_device_dm_subsystem_match(info, "mpath")

def udev_device_is_dm_anaconda(info):
    """ Return True if the device is an anaconda disk image. """
    return udev_device_dm_subsystem_match(info, "anaconda")

def udev_device_is_dm_livecd(info):
    """ Return True if the device is a livecd OS image. """
    # return udev_device_dm_subsystem_match(info, "livecd")
    return (udev_device_is_dm(info) and
            udev_device_get_name(info).startswith("live"))

def udev_device_is_biosraid_member(info):
    # Note that this function does *not* identify raid sets.
    # Tests to see if device is part of a dmraid set.
    # dmraid and mdraid have the same ID_FS_USAGE string, ID_FS_TYPE has a
    # string that describes the type of dmraid (isw_raid_member...),  I don't
    # want to maintain a list and mdraid's ID_FS_TYPE='linux_raid_member', so
    # dmraid will be everything that is raid and not linux_raid_member
    from formats.dmraid import DMRaidMember
    from formats.mdraid import MDRaidMember
    if info.has_key("ID_FS_TYPE") and \
            (info["ID_FS_TYPE"] in DMRaidMember._udevTypes or \
             info["ID_FS_TYPE"] in MDRaidMember._udevTypes) and \
            info["ID_FS_TYPE"] != "linux_raid_member":
        return True

    return False

def udev_device_get_dm_partition_disk(info):
    return re.sub(r'\d*$', '', udev_device_get_name(info))

def udev_device_is_dm_partition(info):
    return (udev_device_is_dm(info) and
            info.get("DM_UUID", "").split("-")[0].startswith("part"))

def udev_device_is_multipath_member(info):
    """ Return True if the device is part of a multipath. """
    return info.get("ID_FS_TYPE") == "multipath_member"

def udev_device_get_multipath_name(info):
    """ Return the name of the multipath that the device is a member of. """
    if udev_device_is_multipath_member(info):
        return info['ID_MPATH_NAME']
    return None

# iscsi disks' ID_PATH form depends on the driver:
# for software iscsi:
# ip-${iscsi_address}:${iscsi_port}-iscsi-${iscsi_tgtname}-lun-${lun}
# for partial offload iscsi:
# pci-${pci_address}-ip-${iscsi_address}:${iscsi_port}-iscsi-${iscsi_tgtname}-lun-${lun}
# Note that in the case of IPV6 iscsi_address itself can contain :
# too, but iscsi_port never contains :

def udev_device_is_sw_iscsi(info):
    # software iscsi
    try:
        path_components = udev_device_get_path(info).split("-")

        if info["ID_BUS"] == "scsi" and len(path_components) >= 6 and \
                path_components[0] == "ip" and path_components[2] == "iscsi":
            return True
    except KeyError:
        pass

    return False

def udev_device_is_partoff_iscsi(info):
    # partial offload iscsi
    try:
        path_components = udev_device_get_path(info).split("-")

        if info["ID_BUS"] == "scsi" and len(path_components) >= 8 and \
                path_components[2] == "ip" and path_components[4] == "iscsi":
            return True
    except KeyError:
        pass

    return False

def udev_device_is_iscsi(info):
    return udev_device_is_sw_iscsi(info) or udev_device_is_partoff_iscsi(info)

def udev_device_get_iscsi_name(info):
    name_field = 3
    if udev_device_is_partoff_iscsi(info):
        name_field = 5

    path_components = udev_device_get_path(info).split("-")

    # Tricky, the name itself contains atleast 1 - char
    return "-".join(path_components[name_field:len(path_components)-2])

def udev_device_get_iscsi_address(info):
    address_field = 1
    if udev_device_is_partoff_iscsi(info):
        address_field = 3

    path_components = udev_device_get_path(info).split("-")

    # IPV6 addresses contain : within the address, so take everything
    # before the last : as address
    return ":".join(path_components[address_field].split(":")[:-1])

def udev_device_get_iscsi_port(info):
    address_field = 1
    if udev_device_is_partoff_iscsi(info):
        address_field = 3

    path_components = udev_device_get_path(info).split("-")

    # IPV6 contains : within the address, the part after the last : is the port
    return path_components[address_field].split(":")[-1]

def udev_device_get_iscsi_session(info):
    # '/devices/pci0000:00/0000:00:02.0/0000:09:00.0/0000:0a:01.0/0000:0e:00.2/host3/session1/target3:0:0/3:0:0:0/block/sda'
    # The position of sessionX part depends on device
    # (e.g. offload vs. sw; also varies for different offload devs)
    session = None
    match = re.match('/.*/(session\d+)', info["sysfs_path"])
    if match:
        session = match.groups()[0]
    else:
        log.error("udev_device_get_iscsi_session: session not found in %s" % info)
    return session


def udev_device_get_iscsi_nic(info):
    iface = None
    session = udev_device_get_iscsi_session(info)
    if session:
        iface = open("/sys/class/iscsi_session/%s/ifacename" %
                     session).read().strip()
    return iface

def udev_device_get_iscsi_initiator(info):
    initiator = None
    if udev_device_is_partoff_iscsi(info):
        host = re.match('.*/(host\d+)', info["sysfs_path"]).groups()[0]
        if host:
            initiator_file = "/sys/class/iscsi_host/%s/initiatorname" % host
            if os.access(initiator_file, os.R_OK):
                initiator = open(initiator_file).read().strip()
                log.debug("found offload iscsi initiatorname %s in file %s" %
                          (initiator, initiator_file))
                if initiator.lstrip("(").rstrip(")").lower() == "null":
                    initiator = None
    if initiator is None:
        session = udev_device_get_iscsi_session(info)
        if session:
            initiator = open("/sys/class/iscsi_session/%s/initiatorname" %
                             session).read().strip()
            log.debug("found iscsi initiatorname %s" % initiator)
    return initiator


# fcoe disks have ID_PATH in the form of:
# For FCoE directly over the NIC (so no VLAN and thus no DCB):
# pci-eth#-fc-${id}
# For FCoE over a VLAN (the DCB case)
# fc-${id}
# fcoe parts look like this:
# pci-eth#-fc-${id}-part#
# fc-${id}-part#

# For the FCoE over VLAN case we also do some checks on the sysfs_path as
# the ID_PATH does not contain all info we need there, the sysfs_path for
# an fcoe disk over VLAN looks like this:
# /devices/virtual/net/eth4.802-fcoe/host3/rport-3:0-4/target3:0:1/3:0:1:0/block/sde
# And for a partition:
# /devices/virtual/net/eth4.802-fcoe/host3/rport-3:0-4/target3:0:1/3:0:1:0/block/sde/sde1

# This is completely different for Broadcom FCoE devices (bnx2fc), where we use
# the sysfs path:
# /devices/pci0000:00/0000:00:02.0/0000:09:00.0/0000:0a:01.0/0000:0e:00.0/host3/rport-3:0-2/target3:0:1/3:0:1:3/block/sdm
# and find whether the host has 'fc_host' and if it the device has a bound
# Ethernet interface.

def _detect_broadcom_fcoe(info):
    re_pci_host=re.compile('/(.*)/(host\d+)')
    match = re_pci_host.match(info["sysfs_path"])
    if match:
        sysfs_pci, host = match.groups()
        if os.access('/sys/%s/%s/fc_host' %(sysfs_pci, host), os.X_OK) and \
                os.access('/sys/%s/net' %(sysfs_pci), os.X_OK):
            return (sysfs_pci, host)
    return (None, None)

def udev_device_is_fcoe(info):
    if info.get("ID_BUS") != "scsi":
        return False

    path = info.get("ID_PATH", "")
    path_components = path.split("-")

    if path.startswith("pci-eth") and len(path_components) >= 4 and \
       path_components[2] == "fc":
        return True

    if path.startswith("fc-") and "fcoe" in info["sysfs_path"]:
        return True

    if _detect_broadcom_fcoe(info) != (None, None):
        return True

    return False

def udev_device_get_fcoe_nic(info):
    path = info.get("ID_PATH", "")
    path_components = path.split("-")

    if path.startswith("pci-eth") and len(path_components) >= 4 and \
       path_components[2] == "fc":
        return path_components[1]

    if path.startswith("fc-") and "fcoe" in info["sysfs_path"]:
        return info["sysfs_path"].split("/")[4].split(".")[0]

    (sysfs_pci, host) = _detect_broadcom_fcoe(info)
    if (sysfs_pci, host) != (None, None):
        net_path = '/sys/%s/net' % sysfs_pci
        listdir = os.listdir(net_path)
        if len(listdir) > 0 :
            return listdir[0]

def udev_device_get_fcoe_identifier(info):
    path = info.get("ID_PATH", "")
    path_components = path.split("-")

    if path.startswith("pci-eth") and len(path_components) >= 4 and \
       path_components[2] == "fc":
        return path_components[3]

    if path.startswith("fc-") and "fcoe" in info["sysfs_path"]:
        return path_components[1]

    if udev_device_is_fcoe(info) and len(path_components) >= 4 and \
       path_components[2] == 'fc':
        return path_components[3]
