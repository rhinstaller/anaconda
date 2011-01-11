
import re

from ..udev import *
import iutil
import logging

log = logging.getLogger("storage")

def _filter_out_mpath_devices(devices):
    retval = []
    for d in devices:
        if udev_device_is_dm_mpath(d):
            log.debug("filtering out coalesced mpath device: %s" % d['name'])
        else:
            retval.append(d)
    return retval

def _filter_out_mpath_partitions(devices, multipaths):
    """
    Use serial numbers of the multipath members to filter devices from the
    devices list. The returned list will only partitions that are NOT partitions
    of the multipath members.
    """
    serials = set(udev_device_get_serial(d)
                  for mpath_members in multipaths for d in mpath_members)
    retval = []
    for d in devices:
        if udev_device_get_serial(d) in serials:
            log.debug("filtering out mpath partition: %s" % d['name'])
        else:
            retval.append(d)
    return retval

def parseMultipathOutput(output):
    """
    Parse output from "multipath -d" or "multipath -ll" and form a topology.

    Returns a dictionary:
    {'mpatha':['sdb','sdc'], 'mpathb': ['sdd', 'sde'], ... }

    The 'multipath -d' output looks like:
    create: mpathc (1ATA     ST3120026AS                                         5M) undef ATA,ST3120026AS
    size=112G features='0' hwhandler='0' wp=undef
    `-+- policy='round-robin 0' prio=1 status=undef
    `- 2:0:0:0 sda 8:0  undef ready running
    create: mpathb (36006016092d21800703762872c60db11) undef DGC,RAID 5
    size=10G features='1 queue_if_no_path' hwhandler='1 emc' wp=undef
    `-+- policy='round-robin 0' prio=2 status=undef
    |- 6:0:0:0 sdb 8:16 undef ready running
    `- 7:0:0:0 sdc 8:32 undef ready running
    create: mpatha (36001438005deb4710000500000270000) dm-0 HP,HSV400
    size=20G features='0' hwhandler='0' wp=rw
    |-+- policy='round-robin 0' prio=-1 status=active
    | |- 7:0:0:1 sda 8:0  active undef running
    | `- 7:0:1:1 sdb 8:16 active undef running
    `-+- policy='round-robin 0' prio=-1 status=enabled
    |- 7:0:2:1 sdc 8:32 active undef running
    `- 7:0:3:1 sdd 8:48 active undef running

    (In anaconda, the first one there won't be included because we blacklist
    "ATA" as a vendor.)

    The 'multipath -ll' output looks like (notice the missing 'create' before
    'mpatha'):

    mpatha (3600a0b800067fcc9000001694b557dd1) dm-0 IBM,1726-4xx  FAStT
    size=360G features='0' hwhandler='1 rdac' wp=rw
    `-+- policy='round-robin 0' prio=3 status=active
      |- 2:0:0:0 sda 8:0  active ready running
      `- 3:0:0:0 sdb 8:16 active ready running

    """
    mpaths = {}
    if output is None:
        return mpaths

    name = None
    devices = []

    policy = re.compile('^[|+` -]+policy')
    device = re.compile('^[|+` -]+[0-9]+:[0-9]+:[0-9]+:[0-9]+ +([a-zA-Z0-9!/]+)')
    create = re.compile('^(create: )?(mpath\w+)')

    lines = output.split('\n')
    for line in lines:
        pmatch = policy.match(line)
        dmatch = device.match(line)
        cmatch = create.match(line)
        lexemes = line.split()
        if not lexemes:
            break
        if cmatch and cmatch.group(2):
            if name and devices:
                mpaths[name] = devices
                name = None
                devices = []
            name = cmatch.group(2)
        elif lexemes[0].startswith('size='):
            pass
        elif pmatch:
            pass
        elif dmatch:
            devices.append(dmatch.groups()[0].replace('!','/'))

    if name and devices:
        mpaths[name] = devices

    return mpaths

def identifyMultipaths(devices):
    """
    This function does a couple of things:
    1) identifies multipath disks,
    2) sets their ID_FS_TYPE to multipath_member,
    3) removes the individual members of an mpath's partitions as well as any
    coalesced multipath devices:

    The return value is a tuple of 3 lists, the first list containing all
    devices except multipath members and partitions, the second list containing
    only the multipath members and the last list only partitions. Specifically,
    the second list is empty if there are no multipath devices found.

    sample input:
    [sr0, sda, sda1, sdb, sdb1, sdb2, sdc, sdc1, sdd, sdd1, sdd2, dm-0]
    where:
    [sdb, sdc] is a multipath pair
    dm-0 is a mutliapth device already coalesced from [sdb, sdc]

    sample output:
    [sda, sdd], [[sdb, sdc]], [sr0, sda1, sdd1, sdd2]]
    """
    log.info("devices to scan for multipath: %s" % [d['name'] for d in devices])

    with open("/etc/multipath.conf") as conf:
        log.debug("/etc/multipath.conf contents:")
        map(lambda line: log.debug(line.rstrip()), conf)
        log.debug("(end of /etc/multipath.conf)")

    topology = parseMultipathOutput(
        iutil.execWithCapture("multipath", ["-d",]))
    topology.update(parseMultipathOutput(
            iutil.execWithCapture("multipath", ["-ll",])))
    # find the devices that aren't in topology, and add them into it...
    topodevs = reduce(lambda x,y: x.union(y), topology.values(), set())
    for name in set([d['name'] for d in devices]).difference(topodevs):
        topology[name] = [name]

    devmap = {}
    non_disk_devices = {}
    for d in devices:
        if not udev_device_is_disk(d):
            non_disk_devices[d['name']] = d
            log.info("adding %s to non_disk_device list" % (d['name'],))
            continue
        devmap[d['name']] = d

    singlepath_disks = []
    multipaths = []

    for name, disks in topology.items():
        if len(disks) == 1:
            if not non_disk_devices.has_key(disks[0]):
                log.info("adding %s to singlepath_disks" % (disks[0],))
                singlepath_disks.append(devmap[disks[0]])
        else:
            # some usb cardreaders use multiple lun's (for different slots)
            # and report a fake disk serial which is the same for all the
            # lun's (#517603)
            all_usb = True
            # see if we've got any non-disk devices on our mpath list.
            # If so, they're probably false-positives.
            non_disks = False
            for disk in disks:
                d = devmap[disk]
                if d.get("ID_USB_DRIVER") != "usb-storage":
                    all_usb = False
                if (not devmap.has_key(disk)) and non_disk_devices.has_key(disk):
                    log.warning("non-disk device %s is part of an mpath" %
                                (disk,))
                    non_disks = True

            if all_usb:
                log.info("adding multi lun usb mass storage device to singlepath_disks: %s" %
                         (disks,))
                singlepath_disks.extend([devmap[d] for d in disks])
                continue

            if non_disks:
                for disk in disks:
                    if devmap.has_key(disk):
                        del devmap[disk]
                    if topology.has_key(disk):
                        del topology[disk]
                continue

            log.info("found multipath set: %s" % (disks,))
            for disk in disks:
                d = devmap[disk]
                log.info("adding %s to multipath_disks" % (disk,))
                d["ID_FS_TYPE"] = "multipath_member"
                d["ID_MPATH_NAME"] = name

            multipaths.append([devmap[d] for d in disks])

    # singlepaths and partitions should not contain multipath devices:
    singlepath_disks = _filter_out_mpath_devices(singlepath_disks)
    partition_devices = _filter_out_mpath_partitions(
        non_disk_devices.values(), multipaths)

    # this is the list of devices we want to keep from the original
    # device list, but we want to maintain its original order.
    singlepath_disks = filter(lambda d: d in devices, singlepath_disks)
    #multipaths = filter(lambda d: d in devices, multipaths)
    partition_devices = filter(lambda d: d in devices, partition_devices)

    mpathStr = "["
    for mpath in multipaths:
        mpathStr += str([d['name'] for d in mpath])
    mpathStr += "]"

    s = "(%s, %s, %s)" % ([d['name'] for d in singlepath_disks], \
                          mpathStr, \
                          [d['name'] for d in partition_devices])
    log.info("devices post multipath scan: %s" % s)
    return (singlepath_disks, multipaths, partition_devices)

class MultipathConfigWriter:
    def __init__(self):
        self.blacklist_devices = []
        self.mpaths = []

    def addBlacklistDevice(self, device):
        self.blacklist_devices.append(device)

    def addMultipathDevice(self, mpath):
        self.mpaths.append(mpath)

    def write(self):
        # if you add anything here, be sure and also add it to anaconda's
        # multipath.conf
        ret = ''
        ret += """\
# multipath.conf written by anaconda

defaults {
	user_friendly_names yes
}
blacklist {
	devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
	devnode "^hd[a-z]"
	devnode "^dcssblk[0-9]*"
	device {
		vendor "DGC"
		product "LUNZ"
	}
	device {
		vendor "IBM"
		product "S/390.*"
	}
	# don't count normal SATA devices as multipaths
	device {
		vendor  "ATA"
	}
	# don't count 3ware devices as multipaths
	device {
		vendor  "3ware"
	}
	device {
		vendor  "AMCC"
	}
	# nor highpoint devices
	device {
		vendor  "HPT"
	}
"""
        for device in self.blacklist_devices:
            if device.serial:
                ret += '\twwid "%s"\n' % device.serial
            elif device.vendor and device.model:
                ret += '\tdevice {\n'
                ret += '\t\tvendor %s\n' % device.vendor
                ret += '\t\tproduct %s\n' % device.model
                ret += '\t}\n'
        if self.mpaths:
                ret += '\twwid "*"\n'
                ret += '}\n'
                ret += 'blacklist_exceptions {\n'
                for mpath in self.mpaths:
                    for k,v in mpath.config.items():
                        if k == 'wwid':
                            ret += '\twwid "%s"\n' % v
        ret += '}\n'
        ret += 'multipaths {\n'
        for mpath in self.mpaths:
            ret += '\tmultipath {\n'
            for k,v in mpath.config.items():
                if k == 'wwid':
                    ret += '\t\twwid "%s"\n' % v
                else:
                    ret += '\t\t%s %s\n' % (k, v)
            ret += '\t}\n'
        ret += '}\n'

        return ret

    def write_bindings(self):
        ret = "# created by Anaconda\n"
        for mpath in self.mpaths:
            if ('alias' in mpath.config) and ('wwid' in mpath.config):
                ret += "%s %s\n" % (mpath.config['alias'], mpath.config['wwid'])
        return ret
