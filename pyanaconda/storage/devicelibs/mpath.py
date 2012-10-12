
import re

from ..udev import udev_device_is_disk
from pyanaconda import iutil
from pyanaconda.flags import flags
from pyanaconda.anaconda_log import log_method_call

import logging
log = logging.getLogger("storage")

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
    device = re.compile('^[|+` -]+[0-9]+:[0-9]+:[0-9]+:[0-9]+ ([a-zA-Z0-9!/]+)')
    create = re.compile('^(create: )?(mpath\w+|[a-f0-9]+)')

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

class MultipathTopology(object):
    def __init__(self, devices_list):
        self._devices = devices_list
        self._nondisks = []
        self._singlepaths = []
        self._multipaths = [] # mpath members
        self._devmap = {}

        self._build_topology()

    def _build_devmap(self):
        self._devmap = {}
        for dev in self._devices:
            self._devmap[dev['name']] = dev

    def _build_mpath_topology(self):
        with open("/etc/multipath.conf") as conf:
            log.debug("/etc/multipath.conf contents:")
            map(lambda line: log.debug(line.rstrip()), conf)
            log.debug("(end of /etc/multipath.conf)")
        self._mpath_topology = parseMultipathOutput(
            iutil.execWithCapture("multipath", ["-d",]))
        self._mpath_topology.update(parseMultipathOutput(
                iutil.execWithCapture("multipath", ["-ll",])))

        delete_keys = []
        for (mp, disks) in self._mpath_topology.items():
            # single device mpath is not really an mpath, eliminate them:
            if len(disks) < 2:
                log.info("MultipathTopology: not a multipath: %s" % disks)
                delete_keys.append(mp)
                continue
            # some usb cardreaders use multiple lun's (for different slots) and
            # report a fake disk serial which is the same for all the lun's
            # (#517603). find those mpaths and eliminate them:
            only_non_usbs = [d for d in disks if
                             self._devmap[d].get("ID_USB_DRIVER") != "usb-storage"]
            if len(only_non_usbs) == 0:
                log.info("DeviceToppology: found multi lun usb "
                         "mass storage device: %s" % disks)
                delete_keys.append(mp)
        map(lambda key: self._mpath_topology.pop(key), delete_keys)

    def _build_topology(self):
        log_method_call(self)
        self._build_devmap()
        self._build_mpath_topology()

        for dev in self._devices:
            name = dev['name']
            if not udev_device_is_disk(dev):
                self._nondisks.append(name)
                log.info("MultipathTopology: found non-disk device: %s" % name)
                continue
            mpath_name = self.multipath_name(name)
            if mpath_name:
                dev["ID_FS_TYPE"] = "multipath_member"
                dev["ID_MPATH_NAME"] = mpath_name
                log.info("MultipathTopology: found a multipath member of %s: %s " %
                         (mpath_name, name))
                continue
            # it's a disk and not a multipath member (can be a coalesced
            # multipath)
            self._singlepaths.append(name)
            log.info("MultipathTopology: found singlepath device: %s" % name)

    def devices_iter(self):
        """ Generator. Yields all disk devices, mpaths members, coalesced mpath
            devices and partitions.

            This property guarantees the order of the returned devices is the
            same as in the device list passed to the object's constructor.
        """
        for device in self._devices:
            yield device

    def singlepaths_iter(self):
        """ Generator. Yields only the singlepath disks.
        """
        for name in self._singlepaths:
            yield self._devmap[name]

    def multipath_name(self, mpath_member_name):
        """ If the mpath_member_name is a member of a multipath device return
            the name of the device (e.g. mpathc).

            Else return None.
        """
        for (name, members) in self._mpath_topology.items():
            if mpath_member_name in members:
                return name
        return None

    def multipaths_iter(self):
        """Generator. Yields all the multipath members, in a topology.

           Every iteration returns a list of mpath member devices forming a
           multipath.
        """
        for disks in self._mpath_topology.values():
            yield [self._devmap[d] for d in disks]


class MultipathConfigWriter:
    def __init__(self):
        self.blacklist_devices = []
        self.mpaths = []

    def addBlacklistDevice(self, device):
        self.blacklist_devices.append(device)

    def addMultipathDevice(self, mpath):
        self.mpaths.append(mpath)

    def write(self, friendly_names):
        # if you add anything here, be sure and also add it to anaconda's
        # multipath.conf
        ret = ''
        ret += """\
# multipath.conf written by anaconda

defaults {
	user_friendly_names %(friendly_names)s
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
""" % {'friendly_names' : "yes" if friendly_names else "no"}
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

    def writeConfig(self, friendly_names=True):
        if not flags.mpath:
            # not writing out a multipath.conf will effectively blacklist all
            # mpath which will prevent any of them from being activated during
            # install
            return

        cfg = self.write(friendly_names)
        with open("/etc/multipath.conf", "w+") as mpath_cfg:
            mpath_cfg.write(cfg)

def flush_mpaths():
    iutil.execWithRedirect("multipath", ["-F"])
    check_output = iutil.execWithCapture("multipath", ["-ll"]).strip()
    if check_output:
        log.error("multipath: some devices could not be flushed")
