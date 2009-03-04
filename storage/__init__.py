# __init__.py
# Entry point for anaconda's storage configuration module.
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
import time
import stat
import errno
import sys

import isys
import iutil
from constants import *
from pykickstart.constants import *

import storage_log
from errors import *
from devices import *
from devicetree import DeviceTree
from deviceaction import *
from formats import getFormat
from formats import get_device_format_class
from formats import get_default_filesystem_type
from devicelibs.lvm import safeLvmName
from udev import udev_trigger
import iscsi
import zfcp

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def storageInitialize(anaconda):
    anaconda.id.storage.shutdown()

    if anaconda.dir == DISPATCH_BACK:
        return

    # XXX I don't understand why I have to do this
    udev_trigger(subsystem="block")
    anaconda.id.storage.reset()

# dispatch.py helper function
def storageComplete(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        rc = anaconda.intf.messageWindow(_("Installation cannot continue."),
                                _("The storage configuration you have "
                                  "chosen has already been activated. You "
                                  "can no longer return to the disk editing "
                                  "screen. Would you like to continue with "
                                  "the installation process?"),
                                type = "yesno")
        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    if anaconda.isKickstart:
        return

    rc = anaconda.intf.messageWindow(_("Writing storage configuration to disk"),
                                _("The partitioning options you have selected "
                                  "will now be written to disk.  Any "
                                  "data on deleted or reformatted partitions "
                                  "will be lost."),
                                type = "custom", custom_icon="warning",
                                custom_buttons=[_("Go _back"),
                                                _("_Write changes to disk")],
                                default = 0)
    if rc == 0:
        return DISPATCH_BACK


class Storage(object):
    def __init__(self, anaconda):
        self.anaconda = anaconda

        # storage configuration variables
        self.ignoredDisks = []
        self.exclusiveDisks = []
        self.doAutoPart = False
        self.clearPartType = CLEARPART_TYPE_NONE
        self.clearPartDisks = []
        self.encryptedAutoPart = False
        self.encryptionPassphrase = None
        self.encryptionRetrofit = False
        self.reinitializeDisks = False
        self.zeroMbr = None
        self.protectedPartitions = []
        self.autoPartitionRequests = []

        self.__luksDevs = {}

        self.iscsi = iscsi.iscsi()
        self.zfcp = zfcp.ZFCP()

        self._nextID = 0
        self.defaultFSType = get_default_filesystem_type()
        self.defaultBootFSType = get_default_filesystem_type(boot=True)

        self.devicetree = DeviceTree(intf=self.anaconda.intf,
                                     ignored=self.ignoredDisks,
                                     exclusive=self.exclusiveDisks,
                                     zeroMbr=self.zeroMbr,
                                     passphrase=self.encryptionPassphrase,
                                     luksDict=self.__luksDevs)
        self.fsset = FSSet(self.devicetree)

    def doIt(self):
        self.devicetree.processActions()

    @property
    def nextID(self):
        id = self._nextID
        self._nextID += 1
        return id

    def shutdown(self):
        try:
            self.devicetree.teardownAll()
        except Exception as e:
            log.error("failure tearing down device tree: %s" % e)

        self.zfcp.shutdown()

        # TODO: iscsi.shutdown()

    def reset(self):
        """ Reset storage configuration to reflect actual system state.

            This should rescan from scratch but not clobber user-obtained
            information like passphrases, iscsi config, &c

        """
        # save passphrases for luks devices so we don't have to reprompt
        for device in self.devices:
            if device.format.type == "luks" and device.format.exists:
                self.__luksDevs[device.format.uuid] = device.format.__passphrase

        w = self.anaconda.intf.waitWindow(_("Finding Devices"),
                                      _("Finding storage devices..."))
        self.iscsi.startup(self.anaconda.intf)
        self.zfcp.startup()
        self.devicetree = DeviceTree(intf=self.anaconda.intf,
                                     ignored=self.ignoredDisks,
                                     exclusive=self.exclusiveDisks,
                                     zeroMbr=self.zeroMbr,
                                     passphrase=self.encryptionPassphrase,
                                     luksDict=self.__luksDevs)
        self.fsset = FSSet(self.devicetree)
        w.pop()

    @property
    def devices(self):
        """ A list of all the devices in the device tree. """
        devices = self.devicetree.devices.values()
        devices.sort(key=lambda d: d.path)
        return devices

    @property
    def disks(self):
        """ A list of the disks in the device tree.

            Ignored disks are not included.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        disks = self.devicetree.getDevicesByType("disk")
        disks.sort(key=lambda d: d.name)
        return disks

    @property
    def partitions(self):
        """ A list of the partitions in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        partitions = self.devicetree.getDevicesByType("partition")
        partitions.sort(key=lambda d: d.name)
        return partitions

    @property
    def vgs(self):
        """ A list of the LVM Volume Groups in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        vgs = self.devicetree.getDevicesByType("lvmvg")
        vgs.sort(key=lambda d: d.name)
        return vgs

    @property
    def lvs(self):
        """ A list of the LVM Logical Volumes in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        lvs = self.devicetree.getDevicesByType("lvmlv")
        lvs.sort(key=lambda d: d.name)
        return lvs

    @property
    def pvs(self):
        """ A list of the LVM Physical Volumes in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices.values()
        pvs = [d for d in devices if d.format.type == "lvmpv"]
        pvs.sort(key=lambda d: d.name)
        return pvs

    def unusedPVs(self, vg=None):
        unused = []
        for pv in self.pvs:
            used = False
            for _vg in self.vgs:
                if _vg.dependsOn(pv) and _vg != vg:
                    used = True
                    break
                elif _vg == vg:
                    break
            if not used:
                unused.append(pv)
        return unused

    @property
    def mdarrays(self):
        """ A list of the MD arrays in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        arrays = self.devicetree.getDevicesByType("mdarray")
        arrays.sort(key=lambda d: d.name)
        return arrays

    @property
    def mdmembers(self):
        """ A list of the MD member devices in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices.values()
        members = [d for d in devices if d.format.type == "mdmember"]
        members.sort(key=lambda d: d.name)
        return members

    def unusedMDMembers(self, array=None):
        unused = []
        for member in self.mdmembers:
            used = False
            for _array in self.mdarrays:
                if _array.dependsOn(member) and _array != array:
                    used = True
                    break
                elif _array == array:
                    break
            if not used:
                unused.append(member)
        return unused

    @property
    def unusedMDMinors(self):
        """ Return a list of unused minors for use in RAID. """
        raidMinors = range(0,32)
        for array in self.mdarrays:
            if array.minor is not None:
                raidMinors.remove(array.minor)
        return raidMinors

    @property
    def swaps(self):
        """ A list of the swap devices in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices.values()
        swaps = [d for d in devices if d.format.type == "swap"]
        swaps.sort(key=lambda d: d.name)
        return swaps

    def exceptionDisks(self):
        """ Return a list of removable devices to save exceptions to.

            FIXME: This raises the problem that the device tree can be
                   in a state that does not reflect that actual current
                   state of the system at any given point.

                   We need a way to provide direct scanning of disks,
                   partitions, and filesystems without relying on the
                   larger objects' correctness.

                   Also, we need to find devices that have just been made
                   available for the purpose of storing the exception
                   report.
        """
        dests = []
        for device in self.devices:
            if not device.removable:
                continue

            dev = parted.Device(path=device.path)
            disk = parted.Disk(device=dev)
            for part in disk.partitions:
                if part.active and \
                   not part.getFlag(parted.PARTITION_RAID) and \
                   not part.getFlag(parted.PARTITION_LVM) and \
                   part.fileSystemType in ("ext3", "ext2", "fat16", "fat32"):
                    dests.append(part.path, device.name)

            if not parts:
                dests.append(device.path, device.name)

        return dests

    def deviceImmutable(self, device):
        """ Return any reason the device cannot be modified/removed.

            Return False if the device can be removed.

            Devices that cannot be removed include:

                - protected partitions
                - devices that are part of an md array or lvm vg
                - extended partition containing logical partitions that
                  meet any of the above criteria

        """
        if not isinstance(device, Device):
            raise ValueError("arg1 (%s) must be a Device instance" % device)

        if device.name in self.protectedPartitions:
            return _("This partition is holding the data for the hard "
                      "drive install.")
        elif device.type == "partition" and device.isProtected:
            # LDL formatted DASDs always have one partition, you'd have to
            # reformat the DASD in CDL mode to get rid of it
            return _("You cannot delete a partition of a LDL formatted "
                     "DASD.")
        elif device.format.type == "mdmember":
            for array in self.mdarrays:
                if array.dependsOn(device):
                    if array.minor is not None:
                        return _("This device is part of the RAID "
                                 "device %.") % (array.path,)
                    else:
                        return _("This device is part of a RAID device.")
        elif device.format.type == "lvmpv":
            for vg in self.vgs:
                if vg.dependsOn(device):
                    if vg.name is not None:
                        return _("This device is part of the LVM "
                                 "volume group '%s'.") % (vg.name,)
                    else:
                        return _("This device is part of a LVM volume "
                                 "group.")
        elif device.type == "partition" and device.isExtended:
            reasons = {}
            for dep in self.deviceDeps(device):
                reason = self.deviceImmutable(dep)
                if reason:
                    reasons[dep.path] = reason
            if reasons:
                msg =  _("This device is an extended partition which "
                         "contains logical partitions that cannot be "
                         "deleted:\n\n")
                for dev in reasons:
                    msg += "%s: %s" % (dev, reasons[dev])
                return msg

        return False

    def deviceDeps(self, device):
        return self.devicetree.getDependentDevices(device)

    def newPartition(self, *args, **kwargs):
        """ Return a new PartitionDevice instance for configuring. """
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=kwargs.pop("mountpoint",
                                                               None))

        if kwargs.has_key("disks"):
            parents = kwargs.pop("disks")

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = "req%d" % self.nextID

        return PartitionDevice(name, *args, **kwargs)

    def newMDArray(self, *args, **kwargs):
        """ Return a new MDRaidArrayDevice instance for configuring. """
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=kwargs.pop("mountpoint",
                                                               None))

        if kwargs.has_key("minor"):
            minor = str(kwargs.pop("minor"))
        else:
            kwargs["minor"] = str(self.unusedMDMinors[0])

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = "md%s" % kwargs["minor"]

        return MDRaidArrayDevice(name, *args, **kwargs)

    def newVG(self, *args, **kwargs):
        """ Return a new LVMVolumeGroupDevice instance. """
        pvs = kwargs.pop("pvs", [])
        for pv in pvs:
            if pv not in self.devices:
                raise ValueError("pv is not in the device tree")

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = self.createSuggestedVGName(self.anaconda.id.network)

        if name in [d.name for d in self.devices]:
            raise ValueError("name already in use")

        return LVMVolumeGroupDevice(name, pvs, *args, **kwargs)

    def newLV(self, *args, **kwargs):
        """ Return a new LVMLogicalVolumeDevice instance. """
        if kwargs.has_key("vg"):
            vg = kwargs.pop("vg")

        mountpoint = kwargs.pop("mountpoint", None)
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=mountpoint)

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            if kwargs.get("format") and kwargs["format"].type == "swap":
                swap = True
            else:
                swap = False
            name = self.createSuggestedLVName(vg,
                                              swap=swap,
                                              mountpoint=mountpoint)

        if name in [d.name for d in self.devices]:
            raise ValueError("name already in use")

        return LVMLogicalVolumeDevice(name, vg, *args, **kwargs)

    def createDevice(self, device):
        """ Schedule creation of a device.

            TODO: We could do some things here like assign the next
                  available raid minor if one isn't already set.
        """
        self.devicetree.registerAction(ActionCreateDevice(device))
        if device.format.type:
            self.devicetree.registerAction(ActionCreateFormat(device))

    def destroyDevice(self, device):
        """ Schedule destruction of a device. """
        action = ActionDestroyDevice(device)
        self.devicetree.registerAction(action)

    def formatDevice(self, device, format):
        """ Schedule formatting of a device. """
        self.devicetree.registerAction(ActionDestroyFormat(device))
        self.devicetree.registerAction(ActionCreateFormat(device, format))

    def formatByDefault(self, device):
        """Return whether the device should be reformatted by default."""
        formatlist = ['/boot', '/var', '/tmp', '/usr']
        exceptlist = ['/home', '/usr/local', '/opt', '/var/www']

        if not device.format.linuxNative:
            return False

        if device.format.mountable:
            if device.format.mountpoint == "/" or \
               device.format.mountpoint in formatlist:
                return True

            for p in formatlist:
                if device.format.mountpoint.startswith(p):
                    for q in exceptlist:
                        if device.format.mountpoint.startswith(q):
                            return False
                    return True
        elif device.format.type == "swap":
                return True

        # be safe for anything else and default to off
        return False

    def extendedPartitionsSupported(self):
        """ Return whether any disks support extended partitions."""
        for disk in self.disks:
            if disk.partedDisk.supportsFeature(parted.DISK_TYPE_EXTENDED):
                return True
        return False

    def createSuggestedVGName(self, network):
        """ Return a reasonable, unused VG name. """
        # try to create a volume group name incorporating the hostname
        hn = network.hostname
        vgnames = [vg.name for vg in self.vgs]
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

        if vgtemplate not in vgnames:
            return vgtemplate
        else:
            i = 0
            while 1:
                tmpname = "%s%02d" % (vgtemplate, i,)
                if not tmpname in vgnames:
                    break

                i += 1
                if i > 99:
                    tmpname = ""

            return tmpname

    def createSuggestedLVName(self, vg, swap=None, mountpoint=None):
        """ Return a suitable, unused name for a new logical volume. """
        if mountpoint:
            # try to incorporate the mountpoint into the name
            if mountpoint == '/':
                lvtemplate = 'lv_root'
            else:
                tmp = safeLvmName(mountpoint)
                lvtemplate = "lv_%s" % (tmp,)
        else:
            if swap:
                if len(self.swaps):
                    lvtemplate = "lv_swap%02d" % (len(self.swaps),)
                else:
                    lvtemplate = "lv_swap"
            else:
                lvtemplate = "LogVol%02d" % (len(vg.lvs),)

        return lvtemplate

    def sanityCheck(self):
        """ Run a series of tests to verify the storage configuration. """
        log.warning("storage.Storage.sanityCheck is unimplemented")
        return ([], [])

    def isProtected(self, device):
        """ Return True is the device is protected. """
        return device.name in self.protectedPartitions

    def checkNoDisks(self):
        """Check that there are valid disk devices."""
        if not self.disks:
            self.anaconda.intf.messageWindow(_("No Drives Found"),
                               _("An error has occurred - no valid devices were "
                                 "found on which to create new file systems. "
                                 "Please check your hardware for the cause "
                                 "of this problem."))
            return True
        return False


def getReleaseString(mountpoint):
    relName = None
    relVer = None

    filename = "%s/etc/redhat-release" % mountpoint
    if os.access(filename, os.R_OK):
        with open(filename) as f:
            try:
                relstr = f.readline().strip()
            except (IOError, AttributeError):
                relstr = ""

        # get the release name and version
        # assumes that form is something
        # like "Red Hat Linux release 6.2 (Zoot)"
        (product, sep, version) = relstr.partition(" release ")
        if sep:
            relName = product
            relVer = version.split()[0]

    return (relName, relVer)

def findExistingRootDevices(anaconda, upgradeany=False):
    """ Return a list of all root filesystems in the device tree. """
    rootDevs = []

    if not os.path.exists(anaconda.rootPath):
        iutil.mkdirChain(anaconda.rootPath)

    roots = []
    for device in anaconda.id.storage.devicetree.leaves:
        if not device.format.linuxNative or not device.format.mountable:
            continue

        if device.name in anaconda.id.storage.protectedPartitions:
            # can't upgrade the part holding hd: media so why look at it?
            continue

        try:
            device.setup()
        except Exception as e:
            log.warning("setup of %s failed: %s" % (device.name, e))
            continue

        try:
            device.format.mount(options="ro", mountpoint=anaconda.rootPath)
        except Exception as e:
            log.warning("mount of %s as %s failed: %s" % (device.name,
                                                          device.format.type,
                                                          e))
            device.teardown()
            continue

        if os.access(anaconda.rootPath + "/etc/fstab", os.R_OK):
            (product, version) = getReleaseString(anaconda.rootPath)
            if upgradeany or \
               anaconda.id.instClass.productUpgradable(product, version):
                rootDevs.append((device, "%s %s" % (product, version)))

        # this handles unmounting the filesystem
        device.teardown(recursive=True)

    return rootDevs

def mountExistingSystem(anaconda, rootDevice,
                        allowDirty=None, warnDirty=None,
                        readOnly=None):
    """ Mount filesystems specified in rootDevice's /etc/fstab file. """
    rootPath = anaconda.rootPath
    fsset = anaconda.id.storage.fsset
    if readOnly:
        readOnly = "ro"
    else:
        readOnly = ""

    if rootDevice.name in anaconda.id.storage.protectedPartitions and \
       os.path.ismount("/mnt/isodir"):
        isys.mount("/mnt/isodir",
                   rootPath,
                   fstype=rootDevice.format.type,
                   bindMount=True)
    else:
        rootDevice.setup()
        rootDevice.format.mount(chroot=rootPath,
                                mountpoint="/",
                                options=readOnly)

    fsset.parseFSTab(chroot=rootPath)

    # check for dirty filesystems
    dirtyDevs = []
    for device in fsset.devices:
        if not hasattr(device.format, "isDirty"):
            continue

        try:
            device.setup()
        except DeviceError as e:
            # we'll catch this in the main loop
            continue

        if device.format.isDirty:
            log.info("%s contains a dirty %s filesystem" % (device.path,
                                                            device.format.type))
            dirtyDevs.append(device.path)

    messageWindow = anaconda.intf.messageWindow
    if not allowDirty and dirtyDevs:
        messageWindow(_("Dirty File Systems"),
                      _("The following file systems for your Linux system "
                        "were not unmounted cleanly.  Please boot your "
                        "Linux installation, let the file systems be "
                        "checked and shut down cleanly to upgrade.\n"
                        "%s") % "\n".join(dirtyDevs))
        anaconda.id.storage.devicetree.teardownAll()
        sys.exit(0)
    elif warnDirty and dirtyDevs:
        rc = messageWindow(_("Dirty File Systems"),
                           _("The following file systems for your Linux "
                             "system were not unmounted cleanly.  Would "
                             "you like to mount them anyway?\n"
                             "%s") % "\n".join(dirtyDevs),
                             type = "yesno")
        if rc == 0:
            return -1

    if flags.setupFilesystems:
        fsset.mountFilesystems(anaconda, readOnly=readOnly, skipRoot=True)


class BlkidTab(object):
    """ Dictionary-like interface to blkid.tab with device path keys """
    def __init__(self, chroot=""):
        self.chroot = chroot
        self.devices = {}

    def parse(self):
        path = "%s/etc/blkid/blkid.tab" % self.chroot
        log.debug("parsing %s" % path)
        with open(path) as f:
            for line in f.readlines():
                # this is pretty ugly, but an XML parser is more work than
                # is justifiable for this purpose
                if not line.startswith("<device "):
                    continue

                line = line[len("<device "):-len("</device>\n")]
                (data, sep, device) = line.partition(">")
                if not device:
                    continue

                self.devices[device] = {}
                for pair in data.split():
                    try:
                        (key, value) = pair.split("=")
                    except ValueError:
                        continue

                    self.devices[device][key] = value[1:-1] # strip off quotes

    def __getitem__(self, key):
        return self.devices[key]

    def get(self, key, default=None):
        return self.devices.get(key, default)


class CryptTab(object):
    """ Dictionary-like interface to crypttab entries with map name keys """
    def __init__(self, devicetree, blkidTab=None):
        self.devicetree = devicetree
        self.blkidTab = blkidTab
        self.chroot = chroot
        self.mappings = {}

    def parse(self, chroot=""):
        """ Parse /etc/crypttab from an existing installation. """
        if not chroot or not os.path.isdir(chroot):
            chroot = ""

        path = "%s/etc/crypttab" % chroot
        log.debug("parsing %s" % path)
        with open(path) as f:
            for line in f.readlines():
                if not self.blkidTab:
                    try:
                        self.blkidTab = BlkidTab(chroot=chroot)
                        self.blkidTab.parse()
                    except Exception:
                        self.blkidTab = None

                for line in lines:
                    (line, pound, comment) = line.partition("#")
                    fields = line.split()
                    if not 2 <= len(fields) <= 4:
                        continue
                    elif len(fields) == 2:
                        fields.extend(['none', ''])
                    elif len(fields) == 3:
                        fields.append('')

                    (name, devspec, keyfile, options) = fields

                    # resolve devspec to a device in the tree
                    device = resolveDevice(self.devicetree,
                                           devspec,
                                           blkidTab=self.blkidTab)
                    if device:
                        self.mappings[name] = {"device": device,
                                               "keyfile": keyfile,
                                               "options": options}

    def populate(self):
        """ Populate the instance based on the device tree's contents. """
        for device in self.devicetree:
            # XXX should we put them all in there or just the ones that
            #     are part of a device containing swap or a filesystem?
            #
            #       Put them all in here -- we can filter from FSSet
            if device.format.type != "luks":
                continue

            key_file = device.format.keyFile
            if not key_file:
                key_file = "none"

            options = device.format.options
            if not options:
                options = ""

            self.mappings[device.format.mapName] = {"device": device,
                                                    "keyfile": key_file,
                                                    "options": options}

    def crypttab(self):
        """ Write out /etc/crypttab """
        crypttab = ""
        for name in self.mappings:
            entry = self[name]
            crypttab += "%s UUID=%s %s %s" % (name,
                                              entry['device'].format.uuid,
                                              entry['keyfile'],
                                              entry['options'])
        return crypttab                       

    def __getitem__(self, key):
        return self.mappings[key]

    def get(self, key, default=None):
        return self.mappings.get(key, default)

def get_containing_device(path, devicetree):
    """ Return the device that a path resides on. """
    if not os.path.exists(path):
        return None

    st = os.stat(path)
    major = os.major(st.st_dev)
    minor = os.minor(st.st_dev)
    link = "/sys/dev/block/%s:%s" % (major, minor)
    if not os.path.exists(link):
        return None

    try:
        device_name = os.path.basename(os.readlink(link))
    except Exception:
        return None

    return devicetree.getDeviceByName(device_name)


class FSSet(object):
    """ A class to represent a set of filesystems. """
    def __init__(self, devicetree):
        self.devicetree = devicetree
        self.cryptTab = None
        self.blkidTab = None
        self.active = False

    @property
    def devices(self):
        devices = self.devicetree.devices.values()
        devices.sort(key=lambda d: d.path)
        return devices

    @property
    def mountpoints(self):
        filesystems = {}
        for device in self.devices:
            if device.format.mountable and device.format.mountpoint:
                filesystems[device.format.mountpoint] = device
        return filesystems

    def parseFSTab(self, chroot=""):
        """ parse /etc/fstab

            preconditions:
                all storage devices have been scanned, including filesystems
            postconditions:

            FIXME: control which exceptions we raise

            XXX do we care about bind mounts?
                how about nodev mounts?
                loop mounts?
        """
        if not chroot or not os.path.isdir(chroot):
            chroot = ""

        path = "%s/etc/fstab" % chroot
        if not os.access(path, os.R_OK):
            # XXX should we raise an exception instead?
            log.info("cannot open %s for read" % path)
            return

        blkidTab = BlkidTab(chroot=chroot)
        try:
            blkidTab.parse()
            log.debug("blkid.tab devs: %s" % blkidTab.devices.keys())
        except Exception as e:
            log.info("error parsing blkid.tab: %s" % e)
            blkidTab = None

        cryptTab = CryptTab(self.devicetree, blkidTab=blkidTab)
        try:
            cryptTab.parse(chroot=chroot)
            log.debug("crypttab maps: %s" % cryptTab.mappings.keys())
        except Exception as e:
            log.info("error parsing crypttab: %s" % e)
            cryptTab = None

        self.blkidTab = blkidTab
        self.cryptTab = cryptTab

        with open(path) as f:
            log.debug("parsing %s" % path)

            lines = f.readlines()

            # save the original file
            self.origFStab = ''.join(lines)

            for line in lines:
                # strip off comments
                (line, pound, comment) = line.partition("#")
                fields = line.split()

                if not 4 <= len(fields) <= 6:
                    continue
                elif len(fields) == 4:
                    fields.extend([0, 0])
                elif len(fields) == 5:
                    fields.append(0)

                (devspec, mountpoint, fstype, options, dump, passno) = fields

                # find device in the tree
                device = resolveDevice(self.devicetree,
                                       devspec,
                                       cryptTab=cryptTab,
                                       blkidTab=blkidTab)
                if device:
                    # fall through to the bottom of this block
                    pass
                elif devspec.startswith("/dev/loop"):
                    # FIXME: create devices.LoopDevice
                    log.warning("completely ignoring your loop mount")
                elif ":" in devspec:
                    # NFS -- preserve but otherwise ignore
                    device = NFSDevice(devspec,
                                       format=getFormat(fstype,
                                                        device=devspec),
                                       exists=True)
                elif devspec.startswith("/") and fstype == "swap":
                    # swap file
                    device = FileDevice(devspec,
                                        parents=get_containing_device(devspec),
                                        format=getFormat(fstype,
                                                         device=devspec,
                                                         exists=True),
                                        exists=True)
                elif fstype == "bind" or "bind" in options:
                    # bind mount... set fstype so later comparison won't
                    # turn up false positives
                    fstype = "bind"
                    device = FileDevice(devspec,
                                        parents=get_containing_device(devspec),
                                        exists=True)
                    device.format = getFormat("bind",
                                              device=device.path,
                                              exists=True)
                else:
                    # nodev filesystem -- preserve or drop completely?
                    format = getFormat(fstype)
                    if isinstance(format, get_device_format_class("nodev")):
                        device = NoDevice(format)
                    else:
                        device = Device(devspec)

                if device is None:
                    log.error("failed to resolve %s (%s) from fstab" % (devspec,
                                                                        fstype))
                    continue

                # make sure, if we're using a device from the tree, that
                # the device's format we found matches what's in the fstab
                fmt = getFormat(fstype, device=device.path)
                if fmt.type != device.format.type:
                    log.warning("scanned format (%s) differs from fstab "
                                "format (%s)" % (device.format.type, fstype))

                if device.format.mountable:
                    device.format.mountpoint = mountpoint
                    device.format.mountopts = options

                # is this useful?
                try:
                    device.format.options = options
                except AttributeError:
                    pass

                if device not in self.devicetree.devices.values():
                    self.devicetree._addDevice(device)

    def fsFreeSpace(self, chroot='/'):
        space = []
        for device in self.devices:
            if not device.format.mountable or \
               not device.format.status:
                continue

            path = "%s/%s" % (chroot, device.format.mountpoint)
            try:
                space.append((device.format.mountpoint,
                              isys.pathSpaceAvailable(path)))
            except SystemError:
                log.error("failed to calculate free space for %s" % (device.format.mountpoint,))

        space.sort(key=lambda s: s[1])
        return space

    def mtab(self):
        format = "%s %s %s %s 0 0\n"
        mtab = ""
        for device in self.devices:
            if not device.format.status:
                continue
            if not device.format.mountable:
                continue
            if device.format.mountpoint:
                options = device.format.mountopts
                options = options.replace("defaults,", "")
                options = options.replace("defaults", "")
                if options:
                    options = "rw," + options
                else:
                    options = "rw"
                mtab = mtab + format % (device.path,
                                        device.format.mountpoint,
                                        device.format.type,
                                        options)
        return mtab

    def turnOnSwap(self, intf=None, upgrading=None):
        for device in self.swapDevices:
            try:
                device.setup()
                device.format.setup()
            except SuspendError:
                if intf:
                    if upgrading:
                        msg = _("The swap device:\n\n     %s\n\n"
                                "in your /etc/fstab file is currently in "
                                "use as a software suspend device, "
                                "which means your system is hibernating. "
                                "To perform an upgrade, please shut down "
                                "your system rather than hibernating it.") \
                              % device.path
                    else:
                        msg = _("The swap device:\n\n     %s\n\n"
                                "in your /etc/fstab file is currently in "
                                "use as a software suspend device, "
                                "which means your system is hibernating. "
                                "If you are performing a new install, "
                                "make sure the installer is set "
                                "to format all swap devices.") \
                              % device.path

                    intf.messageWindow(_("Error"), msg)
                sys.exit(0)
            except DeviceError as msg:
                if intf:
                    if upgrading:
                        err = _("Error enabling swap device %s: %s\n\n"
                                "The /etc/fstab on your upgrade partition "
                                "does not reference a valid swap "
                                "device.\n\nPress OK to exit the "
                                "installer") % (device.path, msg)
                    else:
                        err = _("Error enabling swap device %s: %s\n\n"
                                "This most likely means this swap "
                                "device has not been initialized.\n\n"
                                "Press OK to exit the installer.") % \
                              (device.path, msg)
                    intf.messageWindow(_("Error"), err)
                sys.exit(0)

    def mountFilesystems(self, anaconda, raiseErrors=None, readOnly=None,
                         skipRoot=False):
        intf = anaconda.intf
        for device in [d for d in self.devices if d.isleaf]:
            if not device.format.mountable or not device.format.mountpoint:
                continue

            if skipRoot and device.format.mountpoint == "/":
                continue

            options = device.format.options
            if "noauto" in options.split(","):
                continue

            try:
                device.setup()
            except Exception as msg:
                # FIXME: need an error popup
                continue

            if readOnly:
                options = "%s,%s" % (options, readOnly)

            try:
                device.format.setup(options=options,
                                    chroot=anaconda.rootPath)
            except OSError as (num, msg):
                if intf:
                    if num == errno.EEXIST:
                        intf.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s.  Some element of "
                                             "this path is not a directory. "
                                             "This is a fatal error and the "
                                             "install cannot continue.\n\n"
                                             "Press <Enter> to exit the "
                                             "installer.")
                                           % (device.format.mountpoint,))
                    else:
                        intf.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s: %s.  This is "
                                             "a fatal error and the install "
                                             "cannot continue.\n\n"
                                             "Press <Enter> to exit the "
                                             "installer.")
                                            % (device.format.mountpoint, msg))
                log.error("OSError: (%d) %s" % (num, msg) )
                sys.exit(0)
            except SystemError as (num, msg):
                if raiseErrors:
                    raise
                if intf and not device.format.linuxNative:
                    ret = intf.messageWindow(_("Unable to mount filesystem"),
                                             _("An error occurred mounting "
                                             "device %s as %s.  You may "
                                             "continue installation, but "
                                             "there may be problems.") %
                                             (device.path,
                                              device.format.mountpoint),
                                             type="custom",
                                             custom_icon="warning",
                                             custom_buttons=[_("_Exit installer"),
                                                            _("_Continue")])

                    if ret == 0:
                        sys.exit(0)
                    else:
                        continue

                log.error("SystemError: (%d) %s" % (num, msg) )
                sys.exit(0)
            except FSError as msg:
                if intf:
                    intf.messageWindow(_("Unable to mount filesystem"),
                                       _("An error occurred mounting "
                                         "device %s as %s: %s. This is "
                                         "a fatal error and the install "
                                         "cannot continue.\n\n"
                                         "Press <Enter> to exit the "
                                         "installer.")
                                        % (device.path,
                                           device.format.mountpoint,
                                           msg))
                log.error("FSError: %s" % msg)
                sys.exit(0)

        self.active = True

    def umountFilesystems(self, instPath, ignoreErrors=True, swapoff=True):
        # XXX if we tracked the /dev bind mount this wouln't be necessary
        if os.path.ismount("%s/dev" % instPath):
            isys.umount("%s/dev" % instPath, removeDir=0)

        # reverse works in place so we take a slice
        devices = self.devices[:]
        devices.reverse()
        for device in [d for d in devices if d.isleaf]:
            if not device.format.mountable and \
               (device.format.type != "swap" or swapoff):
                continue

            device.teardownFormat()
            device.teardown()

        self.active = False

    def createSwapFile(self, rootPath, device, size):
        """ Create and activate a swap file under rootPath. """
        filename = "/SWAP"
        count = 0
        basedir = os.path.normpath("%s/%s" % (rootPath,
                                              device.format.mountpoint))
        while os.path.exists("%s/%s" % (basedir, filename)) or \
              self.devicetree.getDeviceByName(filename):
            file = os.path.normpath("%s/%s" % (basedir, filename))
            count += 1
            filename = "/SWAP-%d" % count

        dev = FileDevice(filename,
                         size=size,
                         parents=[device],
                         format=getFormat("swap", device=filename))
        dev.create()
        dev.setup()
        dev.format.create()
        dev.format.setup()
        # nasty, nasty
        self.devicetree._addDevice(dev)

    def mkDevRoot(self, instPath):
        root = self.rootDevice
        dev = "%s/%s" % (instPath, root.path)
        if not os.path.exists("%s/dev/root" %(instPath,)) and os.path.exists(dev):
            rdev = os.stat(dev).st_rdev
            os.mknod("%s/dev/root" % (instPath,), stat.S_IFBLK | 0600, rdev)

    @property
    def swapDevices(self):
        swaps = []
        for device in self.devices:
            if device.format.type == "swap":
                swaps.append(device)
        return swaps

    @property
    def rootDevice(self):
        for device in self.devices:
            try:
                mountpoint = device.format.mountpoint
            except AttributeError:
                mountpoint = None

            if mountpoint == "/":
                return device

    @property
    def migratableDevices(self):
        """ List of devices whose filesystems can be migrated. """
        migratable = []
        for device in self.devices:
            if device.format.migratable and device.format.exists:
                migratable.append(device)

        return migratable

    def write(self, chroot="/"):
        """ write out all config files based on the set of filesystems """
        pass

    def crypttab(self):
        # if we are upgrading, do we want to update crypttab?
        # gut reaction says no, but plymouth needs the names to be very
        # specific for passphrase prompting
        if not self.cryptTab:
            self.cryptTab = CryptTab(self.devicetree)
            self.cryptTab.populate()

        # prune crypttab -- only mappings required by one or more entries
        for name in self.cryptTab.mappings:
            keep = False
            mapInfo = self.cryptTab[name]
            cryptoDev = mapInfo['device']
            for device in self.devices:
                if device.dependsOn(cryptoDev):
                    keep = True
                    break

            if not keep:
                del self.cryptTab.mappings[name]

        return self.cryptTab.crypttab()

    def mdadmConf(self):
        """ Return the contents of mdadm.conf. """
        arrays = self.devicetree.getDevicesByType("mdarray")
        conf = ""
        for array in arrays:
            writeConf = False
            if array in self.devices:
                writeConf = True
            else:
                for device in self.devices:
                    if device.dependsOn(array):
                        writeConf = True
                        break

            if writeConf:
                conf += array.mdadmConfEntry

        return conf

    def writeFSTab(self, chroot="/"):
        """ Write out /etc/fstab. """
        pass

    def fstab (self):
        format = "%-23s %-23s %-7s %-15s %d %d\n"
        fstab = """
#
# /etc/fstab
# Created by anaconda on %s
#
# Accessible filesystems, by reference, are maintained under '/dev/disk'
# See man pages fstab(5), findfs(8), mount(8) and/or vol_id(8) for more info
#
""" % time.asctime()

        for device in self.devices:
            # why the hell do we put swap in the fstab, anyway?
            if not device.format.mountable and device.format.type != "swap":
                continue

            fstype = device.format.type
            if fstype == "swap":
                mountpoint = "swap"
                options = device.format.options
            else:
                mountpoint = device.format.mountpoint
                options = device.format.mountopts
                if not mountpoint:
                    log.warning("%s filesystem on %s has no mountpoint" % \
                                                            (fstype,
                                                             device.path))
                    continue

            options = options or "defaults"
            devspec = device.fstabSpec
            dump = device.format.dump
            if device.format.check and mountpoint == "/":
                passno = 1
            elif device.format.check:
                passno = 2
            else:
                passno = 0
            fstab = fstab + device.fstabComment
            fstab = fstab + format % (devspec, mountpoint, fstype,
                                      options, dump, passno)
        return fstab

def resolveDevice(tree, devspec, blkidTab=None, cryptTab=None):
    # find device in the tree
    device = None
    if devspec.startswith("UUID="):
        # device-by-uuid
        uuid = devspec.partition("=")[2]
        device = tree.uuids.get(uuid)
        if device is None:
            log.error("failed to resolve device %s" % devspec)
    elif devspec.startswith("LABEL="):
        # device-by-label
        label = devspec.partition("=")[2]
        device = tree.fslabels.get(label)
        if device is None:
            log.error("failed to resolve device %s" % devspec)
    elif devspec.startswith("/dev/"):
        # device path
        device = tree.devices.get(devspec)
        if device is None:
            if blkidTab:
                # try to use the blkid.tab to correlate the device
                # path with a UUID
                blkidTabEnt = blkidTab.get(devspec)
                if blkidTabEnt:
                    log.debug("found blkid.tab entry for '%s'" % devspec)
                    uuid = blkidTabEnt.get("UUID")
                    if uuid:
                        device = tree.getDeviceByUuid(uuid)
                        if device:
                            devstr = device.name
                        else:
                            devstr = "None"
                        log.debug("found device '%s' in tree" % devstr)
                    if device and device.format and \
                       device.format.type == "luks":
                        map_name = device.format.mapName
                        log.debug("luks device; map name is '%s'" % map_name)
                        mapped_dev = tree.getDeviceByName(map_name)
                        if mapped_dev:
                            device = mapped_dev

            if device is None and cryptTab and \
               devspec.startswith("/dev/mapper/"):
                # try to use a dm-crypt mapping name to 
                # obtain the underlying device, possibly
                # using blkid.tab
                cryptTabEnt = cryptTab.get(devspec.split("/")[-1])
                if cryptTabEnt:
                    luks_dev = cryptTabEnt['device']
                    try:
                        device = tree.getChildren(luks_dev)[0]
                    except IndexError as e:
                        pass
            elif device is None:
                # dear lvm: can we please have a few more device nodes
                #           for each logical volume?
                #           three just doesn't seem like enough.
                name = devspec[5:]      # strip off leading "/dev/"
                (vg_name, slash, lv_name) = name.partition("/")
                if lv_name and not "/" in lv_name:
                    # looks like we may have one
                    lv = "%s-%s" % (vg_name, lv_name)
                    device = tree.getDeviceByName(lv)

    if device:
        log.debug("resolved '%s' to '%s' (%s)" % (devspec, device.name, device.type))
    else:
        log.debug("failed to resolve '%s'" % devspec)
    return device



