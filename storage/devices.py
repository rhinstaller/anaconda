# devices.py
# Device classes for anaconda's storage configuration module.
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


"""
    Device classes for use by anaconda.

    This is the hierarchy of device objects that anaconda will use for
    managing storage devices in the system. These classes will
    individually make use of external support modules as needed to
    perform operations specific to the type of device they represent.

    TODO:
        - see how to do network devices (NetworkManager may help)
          - perhaps just a wrapper here
        - document return values of all methods/functions
        - find out what other kinds of wild and crazy devices we need to
          represent here (iseries? xen? more mainframe? mac? ps?)
            - PReP
              - this is a prime candidate for a PseudoDevice
            - DASD
            - ZFCP
            - XEN

    What specifications do we allow?              new        existing
        partitions                              
            usage                                  +            +
                filesystem, partition type are implicit
            mountpoint                             +            +
            size
                exact                              +            -
                range                              +            -
                resize                             -            +
            format                                 -            +
            encryption                             +            +

            disk                                                 
                exact                              +            -
                set                                +            -
                    how will we specify this?
                        partition w/ multiple parents cannot otherwise occur
            primary                                +            -

        mdraid sets
            filesystem (*)                         +            +
            mountpoint                             +            +
            size?                                                
            format                                 -            +
            encryption                             +            +

            level                                  +            ? 
            device minor                           +            ? 
            member devices                         +            ? 
            spares                                 +            ? 
            name?
            bitmap? (boolean)                      +            -

        volume groups
            name                                   +            - 
            member pvs                             +            +
            pesize                                 +            ?

        logical volumes
            filesystem                             +            +
            mountpoint                             +            +
            size
                exact                              +            ?
            format                                 -            +
            encryption                             +            +

            name                                   +            ?
            vgname                                 +            ?


"""

import os
import math
import copy

# device backend modules
from devicelibs import mdraid
from devicelibs import lvm
from devicelibs import dm
import parted
import _ped
import platform

from errors import *
from iutil import log_method_call, notify_kernel, numeric_type
from udev import udev_settle
from formats import get_device_format_class, getFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def get_device_majors():
    majors = {}
    for line in open("/proc/devices").readlines():
        try:
            (major, device) = line.split()
        except ValueError:
            continue
        try:
            majors[int(major)] = device
        except ValueError:
            continue
    return majors
device_majors = get_device_majors()


class Device(object):
    """ A generic device.

        Device instances know which devices they depend upon (parents
        attribute). They do not know which devices depend upon them, but
        they do know whether or not they have any dependent devices
        (isleaf attribute).

        A Device's setup method should set up all parent devices as well
        as the device itself. It should not run the resident format's
        setup method.

            Which Device types rely on their parents' formats being active?
                DMCryptDevice

        A Device's teardown method should accept the keyword argument
        recursive, which takes a boolean value and indicates whether or
        not to recursively close parent devices.

        A Device's create method should create all parent devices as well
        as the device itself. It should also run the Device's setup method
        after creating the device. The create method should not create a
        device's resident format.

            Which device type rely on their parents' formats to be created
            before they can be created/assembled?
                VolumeGroup
                DMCryptDevice

        A Device's destroy method should destroy any resident format
        before destroying the device itself.

    """
    _type = "generic device"
    _packages = []

    def __init__(self, name, parents=None, description=''):
        """ Create a Device instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                parents -- a list of required Device instances
                description -- a string describing the device

        """
        self._name = name
        if parents is None:
            parents = []
        elif not isinstance(parents, list):
            raise ValueError("parents must be a list of Device instances")
        self.parents = parents
        self.kids = 0
        self.description = description

        for parent in self.parents:
            parent.addChild()

    def __deepcopy__(self, memo):
        """ Create a deep copy of a Device instance.

            We can't do copy.deepcopy on parted objects, which is okay.
            For these parted objects, we just do a shallow copy.
        """
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        shallow_copy_attrs = ('partedDisk', 'partedDevice',
                             '_partedPartition', '_origPartedDisk')
        for (attr, value) in self.__dict__.items():
            if attr in shallow_copy_attrs:
                setattr(new, attr, copy.copy(value))
            else:
                setattr(new, attr, copy.deepcopy(value, memo))

        return new

    def __str__(self):
        s = ("%(type)s instance (%(id)s) --\n"
             "  description = %(descr)s  name = %(name)s  status = %(status)s"
             "  parents = %(parents)s\n"
             "  kids = %(kids)s\n" %
             {"type": self.__class__.__name__, "id": "%#x" % id(self),
              "name": self.name, "parents": self.parents, "kids": self.kids,
              "descr": self.description, "status": self.status})
        return s

    def removeChild(self):
        log_method_call(self, name=self.name, kids=self.kids)
        self.kids -= 1

    def addChild(self):
        log_method_call(self, name=self.name, kids=self.kids)
        self.kids += 1

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        raise NotImplementedError("setup method not defined for Device")

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        raise NotImplementedError("teardown method not defined for Device")

    def create(self, intf=None):
        """ Create the device. """
        raise NotImplementedError("create method not defined for Device")

    def destroy(self):
        """ Destroy the device. """
        raise NotImplementedError("destroy method not defined for Device")

    def setupParents(self):
        """ Run setup method of all parent devices. """
        for parent in self.parents:
            parent.setup()

    def teardownParents(self, recursive=None):
        """ Run teardown method of all parent devices. """
        for parent in self.parents:
            parent.teardown(recursive=recursive)

    def createParents(self):
        """ Run create method of all parent devices. """
        log.info("NOTE: recursive device creation disabled")
        for parent in self.parents:
            if not parent.exists:
                raise DeviceError("parent device does not exist")
            #parent.create()

    def dependsOn(self, dep):
        """ Return True if this device depends on dep. """
        # XXX does a device depend on itself?
        if dep in self.parents:
            return True

        for parent in self.parents:
            if parent.dependsOn(dep):
                return True

        return False

    @property
    def status(self):
        """ This device's status.

            For now, this should return a boolean:
                True    the device is open and ready for use
                False   the device is not open
        """
        return False

    @property
    def name(self):
        """ This device's name. """
        return self._name

    @property
    def isleaf(self):
        """ True if this device has no children. """
        return self.kids == 0

    @property
    def typeDescription(self):
        """ String describing the device type. """
        return self._type

    @property
    def type(self):
        """ Device type. """
        return self._type

    @property
    def packages(self):
        """ List of packages required to manage devices of this type.

            This list includes the packages required by this device's
            format type as well those required by all of its parent 
            devices.
        """
        packages = self._packages
        packages.extend(self.format.packages)
        for parent in self.parents:
            for package in parent.packages:
                if package not in packages:
                    packages.append(package)

            for package in parent.format.packages:
                if package not in packages:
                    packages.append(package)

        return packages

    @property
    def mediaPresent(self):
        return True


class NetworkStorageDevice(object):
    """ Virtual base class for network backed storage devices """

    def __init__(self, host_address):
        """ Create a NetworkStorage Device instance. Note this class is only
            to be used as a baseclass and then only with multiple inheritance.
            The only correct use is:
            class MyStorageDevice(StorageDevice, NetworkStorageDevice):

            The sole purpose of this class is to:
            1) Be able to check if a StorageDevice is network backed
               (using isinstance).
            2) To be able to get the host address of the host (server) backing
               the storage.

            Arguments:

                host_address -- host address of the backing server
        """
        self.host_address = host_address


class StorageDevice(Device):
    """ A generic storage device.

        A fully qualified path to the device node can be obtained via the
        path attribute, although it is not guaranteed to be useful, or
        even present, unless the StorageDevice's setup method has been
        run.

        StorageDevice instances can optionally contain a filesystem,
        represented by an FS instance. A StorageDevice's create method
        should create a filesystem if one has been specified.
    """
    _type = "storage device"
    _devDir = "/dev"
    sysfsBlockDir = "class/block"
    _resizable = False

    def __init__(self, device, format=None,
                 size=None, major=None, minor=None,
                 sysfsPath='', parents=None, exists=None):
        """ Create a StorageDevice instance.

            Arguments:

                device -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                major -- the device major
                minor -- the device minor
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                description -- a string describing the device

        """
        # allow specification of individual parents
        if isinstance(parents, Device):
            parents = [parents]

        Device.__init__(self, device, parents=parents)

        self.uuid = None
        self._format = None
        self._size = numeric_type(size)
        self.major = numeric_type(major)
        self.minor = numeric_type(minor)
        self.sysfsPath = sysfsPath
        self.exists = exists

        # this may be handy for disk, dmraid, mpath, mdraid
        self.diskLabel = None

        self.format = format
        self.fstabComment = ""
        self._targetSize = self._size

    def _getTargetSize(self):
        return self._targetSize

    def _setTargetSize(self, newsize):
        self._targetSize = newsize

    targetSize = property(lambda s: s._getTargetSize(),
                          lambda s, v: s._setTargetSize(v),
                          doc="Target size of this device")

    def __str__(self):
        s = Device.__str__(self)
        s += ("  uuid = %(uuid)s  format = %(format)r  size = %(size)s\n"
              "  major = %(major)s  minor = %(minor)r  exists = %(exists)s\n"
              "  sysfs path = %(sysfs)s  label = %(diskLabel)s\n"
              "  target size = %(targetSize)s  path = %(path)s\n"
              "  format args = %(formatArgs)s" %
              {"uuid": self.uuid, "format": self.format, "size": self.size,
               "major": self.major, "minor": self.minor, "exists": self.exists,
               "sysfs": self.sysfsPath, "diskLabel": self.diskLabel,
               "targetSize": self.targetSize, "path": self.path,
               "formatArgs": self.formatArgs})
        return s

    @property
    def path(self):
        """ Device node representing this device. """
        return "%s/%s" % (self._devDir, self.name)

    def probe(self):
        """ Probe for any missing information about this device. """
        raise NotImplementedError("probe method not defined for StorageDevice")

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        path = os.path.join("/sys", self.sysfsBlockDir, self.name)
        self.sysfsPath = os.path.realpath(path)[4:]
        log.debug("%s sysfsPath set to %s" % (self.name, self.sysfsPath))

    @property
    def formatArgs(self):
        """ Device-specific arguments to format creation program. """
        return []

    @property
    def resizable(self):
        """ Can this type of device be resized? """
        return self._resizable and self.exists

    def notifyKernel(self):
        """ Send a 'change' uevent to the kernel for this device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            log.debug("not sending change uevent for non-existent device")
            return

        if not self.status:
            log.debug("not sending change uevent for inactive device")
            return

        path = os.path.normpath("/sys/%s" % self.sysfsPath)
        try:
            notify_kernel(path, action="change")
        except Exception, e:
            log.warning("failed to notify kernel of change: %s" % e)

    @property
    def fstabSpec(self):
        spec = self.path
        if self.format and self.format.uuid:
            spec = "UUID=%s" % self.format.uuid
        return spec

    def resize(self, intf=None):
        """ Resize the device.

            New size should already be set.
        """
        raise NotImplementedError("resize method not defined for StorageDevice")

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        self.setupParents()
        for parent in self.parents:
            parent.format.setup()

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists and not recursive:
            raise DeviceError("device has not been created")

        if self.status and self.format.exists:
            self.format.teardown()

        if recursive:
            self.teardownParents(recursive=recursive)

    def _getSize(self):
        """ Get the device's size, accounting for pending changes. """
        size = self._size
        if self.resizable and self.targetSize != size:
            size = self.targetSize
        return size

    def _setSize(self, newsize):
        """ Set the device's size to a new value. """
        if newsize > self.maxSize:
            raise DeviceError("device cannot be larger than %s MB" %
                              (self.maxSize(),))
        self._size = newsize

    size = property(lambda x: x._getSize(),
                    lambda x, y: x._setSize(y),
                    doc="The device's size, accounting for pending changes")

    @property
    def currentSize(self):
        """ The device's actual size. """
        size = 0
        if self.exists:
            size = self._size
        return size

    @property
    def minSize(self):
        """ The minimum size this device can be. """
        if self.exists:
            self.setup()

        if self.format.minSize:
            return self.format.minSize
        else:
            return self.size

    @property
    def maxSize(self):
        """ The maximum size this device can be. """
        if self.format.maxSize > self.currentSize:
            return self.currentSize
        else:
            return self.format.maxSize

    @property
    def status(self):
        """ This device's status.

            For now, this should return a boolean:
                True    the device is open and ready for use
                False   the device is not open
        """
        if not self.exists:
            return False
        return os.access(self.path, os.W_OK)

    def _setFormat(self, format):
        """ Set the Device's format. """
        if not format:
            format = getFormat(None, device=self.path, exists=self.exists)
        log_method_call(self, self.name, type=format.type,
                        current=getattr(self._format, "type", None))
        if self._format and self._format.status:
            # FIXME: self.format.status doesn't mean much
            raise DeviceError("cannot replace active format")

        self._format = format

    def _getFormat(self):
        return self._format

    format = property(lambda d: d._getFormat(),
                      lambda d,f: d._setFormat(f),
                      doc="The device's formatting.")

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device has already been created")

        self.createParents()
        self.setupParents()
        self.exists = True
        self.setup()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if not self.isleaf:
            raise DeviceError("Cannot destroy non-leaf device")

        if self.status:
            # best effort
            self.format.destroy()

        self.exists = False
        # we already did this in DeviceTree._removeDevice
        #for parent in self.parents:
        #    parent.removeChild()

    @property
    def removable(self):
        devpath = os.path.normpath("/sys/%s" % self.sysfsPath)
        remfile = os.path.normpath("%s/removable" % devpath)
        return (self.sysfsPath and os.path.exists(devpath) and
                os.access(remfile, os.R_OK) and
                open(remfile).readline().strip() == "1")

class DiskDevice(StorageDevice):
    """ A disk """
    _type = "disk"

    def __init__(self, device, format=None,
                 size=None, major=None, minor=None, sysfsPath='', \
                 parents=None, initcb=None, initlabel=None):
        """ Create a DiskDevice instance.

            Arguments:

                device -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                major -- the device major
                minor -- the device minor
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                removable -- whether or not this is a removable device

                initcb -- the call back to be used when initiating disk.
                initlabel -- whether to start with a fresh disklabel


            DiskDevices always exist.
        """
        StorageDevice.__init__(self, device, format=format, size=size,
                               major=major, minor=minor, exists=True,
                               sysfsPath=sysfsPath, parents=parents)

        self.partedDevice = None
        self.partedDisk = None

        log.debug("looking up parted Device: %s" % self.path)

        # We aren't guaranteed to be able to get a device.  In particular,
        # built-in USB flash readers show up as devices but do not always
        # have any media present, so parted won't be able to find a device.
        try:
            self.partedDevice = parted.Device(path=self.path)
        except _ped.DeviceException:
            pass

        if self.partedDevice:
            log.debug("creating parted Disk: %s" % self.path)
            if initlabel:
                self.partedDisk = self.freshPartedDisk()
            else:
                try:
                    self.partedDisk = parted.Disk(device=self.partedDevice)
                except _ped.DiskLabelException:
                    # if we have a cb function use it. else an error.
                    if initcb is not None and initcb():
                        self.partedDisk = parted.freshDisk(device=self.partedDevice, \
                                ty = platform.getPlatform(None).diskType)
                    else:
                        raise DeviceUserDeniedFormatError("User prefered to not format.")

        # We save the actual state of the disk here. Before the first
        # modification (addPartition or removePartition) to the partition
        # table we reset self.partedPartition to this state so we can
        # perform the modifications one at a time.
        if self.partedDisk:
            self._origPartedDisk = self.partedDisk.duplicate()
        else:
            self._origPartedDisk = None

        self.probe()

    def __str__(self):
        s = StorageDevice.__str__(self)
        s += ("  removable = %(removable)s  partedDevice = %(partedDevice)r\n"
              "  partedDisk = %(partedDisk)r" %
              {"removable": self.removable, "partedDisk": self.partedDisk,
               "partedDevice": self.partedDevice})
        return s

    def freshPartedDisk(self):
        log_method_call(self, self.name)
        labelType = platform.getPlatform(None).diskType
        return parted.freshDisk(device=self.partedDevice, ty=labelType)

    @property
    def mediaPresent(self):
        return self.partedDevice is not None

    @property
    def size(self):
        """ The disk's size in MB """
        if not self.mediaPresent:
            return 0

        if not self._size:
            self._size = self.partedDisk.device.getSize()
        return self._size

    def resetPartedDisk(self):
        """ Reset parted.Disk to reflect the actual layout of the disk. """
        log_method_call(self, self.name)
        self.partedDisk = self._origPartedDisk

    def removePartition(self, device):
        log_method_call(self, self.name, part=device.name)
        if not self.mediaPresent:
            raise DeviceError("cannot remove partition from disk %s which has no media" % self.name)

        partition = self.partedDisk.getPartitionByPath(device.path)
        if partition:
            self.partedDisk.removePartition(partition)

    def addPartition(self, device):
        log_method_call(self, self.name, part=device.name)
        if not self.mediaPresent:
            raise DeviceError("cannot add partition to disk %s which has no media" % self.name)

        for part in self.partedDisk.partitions:
            log.debug("disk %s: partition %s has geom %s" % (self.name,
                                                             part.getDeviceNodeName(),
                                                             part.geometry))

        geometry = device.partedPartition.geometry
        constraint = parted.Constraint(exactGeom=geometry)
        partition = parted.Partition(disk=self.partedDisk,
                                     type=device.partedPartition.type,
                                     geometry=geometry)
        self.partedDisk.addPartition(partition,
                                     constraint=constraint)

    def probe(self):
        """ Probe for any missing information about this device.

            pyparted should be able to tell us anything we want to know.
            size, disklabel type, maybe even partition layout
        """
        if not self.mediaPresent or not 'parted' in globals().keys():
            return

        log_method_call(self, self.name, size=self.size, partedDevice=self.partedDevice)
        if not self.size:
            self._size = self.partedDevice.getSize()
        if not self.diskLabel:
            log.debug("setting %s diskLabel to %s" % (self.name,
                                                      self.partedDisk.type))
            self.diskLabel = self.partedDisk.type

    def commit(self, intf=None):
        """ Commit changes to the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.mediaPresent:
            raise DeviceError("cannot commit to disk %s which has no media" % self.name)

        self.setupParents()
        self.setup()

        # give committing 5 tries, failing that, raise an exception
        attempt = 1
        maxTries = 5
        keepTrying = True

        while keepTrying and (attempt <= maxTries):
            try:
                self.partedDisk.commit()
                keepTrying = False
            except parted.DiskException as msg:
                log.warning(msg)
                attempt += 1

        if keepTrying:
            raise DeviceError("cannot commit to disk %s after %d attempts" % (self.name, maxTries,))

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.mediaPresent:
            raise DeviceError("cannot destroy disk %s which has no media" % self.name)

        if self.status:
            self.format.destroy()

        self.partedDisk.deleteAllPartitions()
        # this is perhaps a separate operation (wiping the disklabel)
        self.partedDisk.clobber()
        self.partedDisk.commit()
        self.teardown()


    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)
        if not os.path.exists(self.path):
            raise DeviceError("device does not exist")


class PartitionDevice(StorageDevice):
    """ A disk partition.

        On types and flags...

        We don't need to deal with numerical partition types at all. The
        only type we are concerned with is primary/logical/extended. Usage
        specification is accomplished through the use of flags, which we
        will set according to the partition's format.
    """
    _type = "partition"
    _resizable = True

    def __init__(self, name, format=None,
                 size=None, grow=False, maxsize=None,
                 major=None, minor=None, bootable=None,
                 sysfsPath='', parents=None, exists=None,
                 partType=None, primary=False):
        """ Create a PartitionDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                exists -- indicates whether this is an existing device
                format -- the device's format (DeviceFormat instance)

                For existing partitions:

                    parents -- the disk that contains this partition
                    major -- the device major
                    minor -- the device minor
                    sysfsPath -- sysfs device path

                For new partitions:

                    partType -- primary,extended,&c (as parted constant)
                    grow -- whether or not to grow the partition
                    maxsize -- max size for growable partitions (in MB)
                    size -- the device's size (in MB)
                    bootable -- whether the partition is bootable
                    parents -- a list of potential containing disks
        """
        self.req_disks = []
        self.req_partType = None
        self.req_primary = None
        self.req_grow = None
        self.req_bootable = None
        self.req_size = 0
        self.req_base_size = 0
        self.req_max_size = 0

        self._bootable = False

        self._resize = False

        StorageDevice.__init__(self, name, format=format, size=size,
                               major=major, minor=minor, exists=exists,
                               sysfsPath=sysfsPath, parents=parents)

        if not exists:
            # this is a request, not a partition -- it has no parents
            self.req_disks = self.parents[:]
            for dev in self.parents:
                dev.removeChild()
            self.parents = []

        # FIXME: Validate partType, but only if this is a new partition
        #        Otherwise, overwrite it with the partition's type.
        self._partType = None
        self.partedFlags = {}
        self._partedPartition = None

        # FIXME: Validate size, but only if this is a new partition.
        #        For existing partitions we will get the size from
        #        parted.

        if self.exists:
            log.debug("looking up parted Partition: %s" % self.path)
            #self.partedPartition = parted.getPartitionByName(self.path)
            self._partedPartition = self.disk.partedDisk.getPartitionByPath(self.path)
            if not self._partedPartition:
                raise DeviceError("cannot find parted partition instance")

            # collect information about the partition from parted
            self.probe()
        else:
            # XXX It might be worthwhile to create a shit-simple
            #     PartitionRequest class and pass one to this constructor
            #     for new partitions.
            self.req_name = name
            self.req_partType = partType
            self.req_primary = primary
            self.req_max_size = numeric_type(maxsize)
            self.req_grow = grow
            self.req_bootable = bootable

            # req_size may be manipulated in the course of partitioning
            self.req_size = self._size

            # req_base_size will always remain constant
            self.req_base_size = self._size

    def __str__(self):
        s = StorageDevice.__str__(self)
        s += ("  grow = %(grow)s  max size = %(maxsize)s  bootable = %(bootable)s\n"
              "  part type = %(partType)s  primary = %(primary)s\n"
              "  partedPartition = %(partedPart)r  disk = %(disk)r" %
              {"grow": self.req_grow, "maxsize": self.req_max_size,
               "bootable": self.bootable, "partType": self.partType,
               "primary": self.req_primary,
               "partedPart": self.partedPartition, "disk": self.disk})
        return s

    def _setTargetSize(self, newsize):
        if newsize != self.currentSize:
            # change this partition's geometry in-memory so that other
            # partitioning operations can complete (e.g., autopart)
            self._targetSize = newsize
            disk = self.disk.partedDisk

            # resize the partition's geometry in memory
            (constraint, geometry) = self._computeResize(self.partedPartition)
            disk.setPartitionGeometry(partition=self.partedPartition,
                                      constraint=constraint,
                                      start=geometry.start, end=geometry.end)

    @property
    def path(self):
        """ Device node representing this device. """
        if not self.parents:
            # Bogus, but code in various places compares devices by path
            # So we must return something unique
            return self.name

        return "%s/%s" % (self.parents[0]._devDir, self.name)

    @property
    def partType(self):
        """ Get the partition's type (as parted constant). """
        try:
            ptype = self.partedPartition.type
        except AttributeError:
            ptype = self._partType

        if not self.exists and ptype is None:
            ptype = self.req_partType

        return ptype

    @property
    def isExtended(self):
        return self.partType & parted.PARTITION_EXTENDED

    @property
    def isLogical(self):
        return self.partType & parted.PARTITION_LOGICAL

    @property
    def isPrimary(self):
        return self.partType == parted.PARTITION_NORMAL

    @property
    def isProtected(self):
        return self.partType & parted.PARTITION_PROTECTED

    def _getPartedPartition(self):
        if self.disk and not self._partedPartition:
            pdisk = self.disk.partedDisk
            self._partedPartition = pdisk.getPartitionByPath(self.path)

        return self._partedPartition

    def _setPartedPartition(self, partition):
        """ Set this PartitionDevice's parted Partition instance. """
        log_method_call(self, self.name)
        if partition is None:
            path = None
        elif isinstance(partition, parted.Partition):
            path = partition.path
        else:
            raise ValueError("partition must be a parted.Partition instance")

        log.debug("device %s new partedPartition %s has path %s" % (self.name,
                                                                    partition,
                                                                    path))

        if partition is None:
            self._partedPartition = None
            # no need to clobber our name
        else:
            self._partedPartition = partition
            self._name = partition.getDeviceNodeName().split("/")[-1]

    partedPartition = property(lambda d: d._getPartedPartition(),
                               lambda d,p: d._setPartedPartition(p))

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.parents:
            self.sysfsPath = ''

        elif self.parents[0]._devDir == "/dev/mapper":
            dm_node = dm.dm_node_from_name(self.name)
            path = os.path.join("/sys", self.sysfsBlockDir, dm_node)
            self.sysfsPath = os.path.realpath(path)[4:]

        else:
            StorageDevice.updateSysfsPath(self)

    def dependsOn(self, dep):
        """ Return True if this device depends on dep. """
        if isinstance(dep, PartitionDevice) and dep.isExtended and self.isLogical:
            return True

        return Device.dependsOn(self, dep)

    def _setFormat(self, format):
        """ Set the Device's format. """
        log_method_call(self, self.name)
        StorageDevice._setFormat(self, format)

    def _setBootable(self, bootable):
        """ Set the bootable flag for this partition. """
        if self.partedPartition:
            if self.flagAvailable(parted.PARTITION_BOOT):
                if bootable:
                    self.setFlag(parted.PARTITION_BOOT)
                else:
                    self.unsetFlag(parted.PARTITION_BOOT)
            else:
                raise DeviceError(_("boot flag not available for this "
                                    "partition"))

            self._bootable = bootable
        else:
            self.req_bootable = bootable

    def _getBootable(self):
        return self._bootable or self.req_bootable

    bootable = property(_getBootable, _setBootable)

    def flagAvailable(self, flag):
        log_method_call(self, path=self.path, flag=flag,
                        part=self.partedPartition)
        if not self.partedPartition:
            return

        return self.partedPartition.isFlagAvailable(flag)

    def getFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag,
                        part=self.partedPartition)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        return self.partedPartition.getFlag(flag)

    def setFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag,
                        part=self.partedPartition)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        self.partedPartition.setFlag(flag)

    def unsetFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag,
                        part=self.partedPartition)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        self.partedPartition.unsetFlag(flag)

    def probe(self):
        """ Probe for any missing information about this device.

            size, partition type, flags
        """
        log_method_call(self, self.name, exists=self.exists)
        if not self.exists:
            return

        # this is in MB
        self._size = self.partedPartition.getSize()
        self.targetSize = self._size

        self._partType = self.partedPartition.type

        self._bootable = self.getFlag(parted.PARTITION_BOOT)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        self.createParents()
        self.setupParents()

        self.disk.addPartition(self)
        self.disk.commit()

        # this will force a lookup on next access, which we want
        self.partedPartition = None

        self.exists = True
        self.setup()

    def _computeResize(self, partition):
        log_method_call(self, self.name, status=self.status)

        # compute new size for partition
        currentGeom = partition.geometry
        currentDev = currentGeom.device
        newLen = long(self.targetSize * 1024 * 1024) / currentDev.sectorSize
        newGeometry = parted.Geometry(device=currentDev,
                                      start=currentGeom.start,
                                      length=newLen)
        constraint = parted.Constraint(exactGeom=newGeometry)

        return (constraint, newGeometry)

    def resize(self, intf=None):
        """ Resize the device.

            self.targetSize must be set to the new size.
        """
        log_method_call(self, self.name, status=self.status)

        if self.targetSize != self.currentSize:
            # partedDisk has been restored to _origPartedDisk, so
            # recalculate resize geometry because we may have new
            # partitions on the disk, which could change constraints
            partition = self.disk.partedDisk.getPartitionByPath(self.path)
            (constraint, geometry) = self._computeResize(partition)

            self.disk.partedDisk.setPartitionGeometry(partition=partition,
                                                      constraint=constraint,
                                                      start=geometry.start,
                                                      end=geometry.end)

            self.disk.commit()
            self.notifyKernel()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if not self.sysfsPath:
            return

        if not self.isleaf:
            raise DeviceError("Cannot destroy non-leaf device")

        self.setupParents()
        if self.status:
            self.format.destroy()

        self.disk.removePartition(self)
        self.disk.commit()

        self.exists = False

    def _getSize(self):
        """ Get the device's size. """
        size = self._size
        if len(self.parents) == 1:
            # this defaults to MB
            size = self.partedPartition.getSize()
        return size

    def _setSize(self, newsize):
        """ Set the device's size (for resize, not creation).

            Arguments:

                newsize -- the new size (in MB)

        """
        log_method_call(self, self.name,
                        status=self.status, size=self._size, newsize=newsize)
        if not self.exists:
            raise DeviceError("device does not exist")

        if newsize > self.disk.size:
            raise ValueError("partition size would exceed disk size")

        # this defaults to MB
        maxAvailableSize = self.partedPartition.getMaxAvailableSize()

        if newsize > maxAvailableSize:
            raise ValueError("new size is greater than available space")

         # now convert the size to sectors and update the geometry
        geometry = self.partedPartition.geometry
        physicalSectorSize = geometry.device.physicalSectorSize

        new_length = (newsize * (1024 * 1024)) / physicalSectorSize
        geometry.length = new_length

    def _getDisk(self):
        """ The disk that contains this partition."""
        try:
            disk = self.parents[0]
        except IndexError:
            disk = None
        return disk

    def _setDisk(self, disk):
        """Change the parent.

        Setting up a disk is not trivial.  It has the potential to change
        the underlying object.  If necessary we must also change this object.
        """
        log_method_call(self, self.name, old=self.disk, new=disk)
        if self.disk:
            self.disk.removeChild()

        self.parents = [disk]
        disk.addChild()

    disk = property(lambda p: p._getDisk(), lambda p,d: p._setDisk(d))

    @property
    def maxSize(self):
        """ The maximum size this partition can be. """
        # XXX: this is MB by default
        maxPartSize = self.partedPartition.getMaxAvailableSize()

        if self.format.maxSize > maxPartSize:
            return maxPartSize
        else:
            return self.format.maxSize


class DMDevice(StorageDevice):
    """ A device-mapper device """
    _type = "dm"
    _devDir = "/dev/mapper"

    def __init__(self, name, format=None, size=None, dmUuid=None,
                 target=None, exists=None, parents=None, sysfsPath=''):
        """ Create a DMDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                target -- the device-mapper target type (string)
                size -- the device's size (units/format TBD)
                dmUuid -- the device's device-mapper UUID
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                exists -- indicates whether this is an existing device
        """
        StorageDevice.__init__(self, name, format=format, size=size,
                               exists=exists,
                               parents=parents, sysfsPath=sysfsPath)
        self.target = target
        self.dmUuid = dmUuid

    def __str__(self):
        s = StorageDevice.__str__(self)
        s += ("  target = %(target)s  dmUuid = %(dmUuid)s" %
              {"target": self.target, "dmUuid": self.dmUuid})
        return s

    def probe(self):
        """ Probe for any missing information about this device.

            target type, parents?
        """
        raise NotImplementedError("probe method not defined for DMDevice")

    @property
    def fstabSpec(self):
        """ Return the device specifier for use in /etc/fstab. """
        return self.path

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            dm_node = self.getDMNode()
            path = os.path.join("/sys", self.sysfsBlockDir, dm_node)
            self.sysfsPath = os.path.realpath(path)[4:]
        else:
            self.sysfsPath = ''

    #def getTargetType(self):
    #    return dm.getDmTarget(name=self.name)

    def getDMNode(self):
        """ Return the dm-X (eg: dm-0) device node for this device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        return dm.dm_node_from_name(self.name)

    def _setName(self, name):
        """ Set the device's map name. """
        log_method_call(self, self.name, status=self.status)
        if self.status:
            raise DeviceError("device is active")

        self._name = name
        #self.sysfsPath = "/dev/disk/by-id/dm-name-%s" % self.name

    name = property(lambda d: d._name,
                    lambda d,n: d._setName(n))


class DMCryptDevice(DMDevice):
    """ A dm-crypt device """
    _type = "dm-crypt"

    def __init__(self, name, format=None, size=None, uuid=None,
                 exists=None, sysfsPath='', parents=None):
        """ Create a DMCryptDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                exists -- indicates whether this is an existing device
        """
        DMDevice.__init__(self, name, format=format, size=size,
                          parents=parents, sysfsPath=sysfsPath,
                          exists=exists, target="crypt")

class LUKSDevice(DMCryptDevice):
    """ A mapped LUKS device. """
    _type = "luks/dm-crypt"

    def __init__(self, name, format=None, size=None, uuid=None,
                 exists=None, sysfsPath='', parents=None):
        """ Create a LUKSDevice instance.

            Arguments:

                name -- the device name

            Keyword Arguments:

                size -- the device's size in MB
                uuid -- the device's UUID
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                exists -- indicates whether this is an existing device
        """
        DMCryptDevice.__init__(self, name, format=format, size=size,
                               parents=parents, sysfsPath=sysfsPath,
                               uuid=None, exists=exists)

    @property
    def size(self):
        # break off 2KB for the LUKS header
        return float(self.slave.size) - (2.0 / 1024)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        self.createParents()
        self.setupParents()

        #if not self.slave.format.exists:
        #    self.slave.format.create()
        self._name = self.slave.format.mapName
        self.exists = True
        self.setup()

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        self.slave.setup()
        self.slave.format.setup()

    def teardown(self, recursive=False):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists and not recursive:
            raise DeviceError("device has not been created")

        if self.status and self.format.exists:
            self.format.teardown()
            udev_settle()

        if self.slave.format.exists:
            self.slave.format.teardown()

        if recursive:
            self.teardownParents(recursive=recursive)

    def destroy(self):
        log_method_call(self, self.name, status=self.status)
        self.format.teardown()
        self.teardown()

    @property
    def slave(self):
        """ This device's backing device. """
        return self.parents[0]


class LVMVolumeGroupDevice(DMDevice):
    """ An LVM Volume Group

        XXX Maybe this should inherit from StorageDevice instead of
            DMDevice since there's no actual device.
    """
    _type = "lvmvg"

    def __init__(self, name, parents, size=None, free=None,
                 peSize=None, peCount=None, peFree=None, pvCount=None,
                 lvNames=[], uuid=None, exists=None, sysfsPath=''):
        """ Create a LVMVolumeGroupDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)
                parents -- a list of physical volumes (StorageDevice)

            Keyword Arguments:

                peSize -- physical extent size (in MB)
                exists -- indicates whether this is an existing device
                sysfsPath -- sysfs device path

                For existing VG's only:

                    size -- the VG's size (in MB)
                    free -- amount of free space in the VG
                    peFree -- number of free extents
                    peCount -- total number of extents
                    pvCount -- number of PVs in this VG
                    lvNames -- the names of this VG's LVs
                    uuid -- the VG's UUID

        """
        self.pvClass = get_device_format_class("lvmpv")
        if not self.pvClass:
            raise DeviceError("cannot find 'lvmpv' class")

        if isinstance(parents, list):
            for dev in parents:
                if not isinstance(dev.format, self.pvClass):
                    raise ValueError("constructor requires a list of PVs")
        elif not isinstance(parents.format, self.pvClass):
            raise ValueError("constructor requires a list of PVs")

        DMDevice.__init__(self, name, parents=parents,
                          exists=exists, sysfsPath=sysfsPath)

        self.uuid = uuid
        self.free = numeric_type(free)
        self.peSize = numeric_type(peSize)
        self.peCount = numeric_type(peCount)
        self.peFree = numeric_type(peFree)
        self.pvCount = numeric_type(pvCount)
        self.lvNames = lvNames

        # circular references, here I come
        self._lvs = []

        # TODO: validate peSize if given
        if not self.peSize:
            self.peSize = 4.0   # MB

        #self.probe()

    def __str__(self):
        s = DMDevice.__str__(self)
        s += ("  free = %(free)s  PE Size = %(peSize)s  PE Count = %(peCount)s\n"
              "  PE Free = %(peFree)s  PV Count = %(pvCount)s\n"
              "  LV Names = %(lvNames)s  modified = %(modified)s\n"
              "  extents = %(extents)s  free space = %(freeSpace)s\n"
              "  free extents = %(freeExtents)s\n"
              "  PVs = %(pvs)s\n"
              "  LVs = %(lvs)s" %
              {"free": self.free, "peSize": self.peSize, "peCount": self.peCount,
               "peFree": self.peFree, "pvCount": self.pvCount,
               "lvNames": self.lvNames, "modified": self.isModified,
               "extents": self.extents, "freeSpace": self.freeSpace,
               "freeExtents": self.freeExtents, "pvs": self.pvs, "lvs": self.lvs})
        return s

    def probe(self):
        """ Probe for any information about this device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

    @property
    def status(self):
        """ The device's status (True means active). """
        if not self.exists:
            return False

        # certainly if any of this VG's LVs are active then so are we
        for lv in self.lvs:
            if lv.status:
                return True

        # if any of our PVs are not active then we cannot be
        for pv in self.pvs:
            if not pv.status:
                return False

        # if we are missing some of our PVs we cannot be active
        if len(self.pvs) != self.pvCount:
            return False

        return True

    def _addDevice(self, device):
        """ Add a new physical volume device to the volume group.

            XXX This is for use by device probing routines and is not
                intended for modification of the VG.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)
        if not self.exists:
            raise DeviceError("device does not exist")

        if not isinstance(device.format, self.pvClass):
            raise ValueError("addDevice requires a PV arg")

        if self.uuid and device.format.vgUuid != self.uuid:
            raise ValueError("UUID mismatch")

        if device in self.pvs:
            raise ValueError("device is already a member of this VG")

        self.parents.append(device)
        device.addChild()

        # now see if the VG can be activated
        if len(self.parents) == self.pvCount:
            self.setup()

    def _removeDevice(self, device):
        """ Remove a physical volume from the volume group.

            This is for cases like clearing of preexisting partitions.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)
        try:
            self.parents.remove(device)
        except ValueError, e:
            raise ValueError("cannot remove non-member PV device from VG")

        device.removeChild()

    def setup(self, intf=None):
        """ Open, or set up, a device.

            XXX we don't do anything like "vgchange -ay" because we don't
                want all of the LVs activated, just the VG itself.
        """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            return

        if len(self.parents) < self.pvCount:
            raise DeviceError("cannot activate VG with missing PV(s)")

        self.setupParents()

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists and not recursive:
            raise DeviceError("device has not been created")

        if self.status:
            lvm.vgdeactivate(self.name)

        if recursive:
            self.teardownParents(recursive=recursive)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        pv_list = []
        #for pv in self.parents:
            # This is a little bit different from other devices in that
            # for VG we need the PVs to be formatted before we can create
            # the VG.
        #    pv.create()
        #    pv.format.create()
        #    pv_list.append(pv.path)
        pv_list = [pv.path for pv in self.parents]
        self.createParents()
        self.setupParents()
        lvm.vgcreate(self.name, pv_list, self.peSize)
        # FIXME set / update self.uuid here
        self.exists = True
        self.setup()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        self.teardown()

        # this sometimes fails for some reason.
        try:
            lvm.vgreduce(self.name, [], rm=True)
            lvm.vgremove(self.name)
        except lvm.LVMErorr:
            raise DeviceError("Could not completely remove VG %s" % self.name)
        finally:
            self.notifyKernel()
            self.exists = False

    def reduce(self, pv_list):
        """ Remove the listed PVs from the VG. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        lvm.vgreduce(self.name, pv_list)
        # XXX do we need to notify the kernel?

    def _addLogVol(self, lv):
        """ Add an LV to this VG. """
        if lv in self._lvs:
            raise ValueError("lv is already part of this vg")

        # verify we have the space, then add it
        if not lv.exists and lv.size > self.freeSpace:
            raise DeviceError("new lv is too large to fit in free space")

        self._lvs.append(lv)

    def _removeLogVol(self, lv):
        """ Remove an LV from this VG. """
        if lv not in self.lvs:
            raise ValueError("specified lv is not part of this vg")

        self._lvs.remove(lv)

    def _addPV(self, pv):
        """ Add a PV to this VG. """
        if pv in self.pvs:
            raise ValueError("pv is already part of this vg")

        # for the time being we will not allow vgextend
        if self.exists:
            raise DeviceError("cannot add pv to existing vg")

        self.parents.append(pv)
        pv.addChild()

    def _removePV(self, pv):
        """ Remove an PV from this VG. """
        if not pv in self.pvs:
            raise ValueError("specified pv is not part of this vg")

        # for the time being we will not allow vgreduce
        if self.exists:
            raise DeviceError("cannot remove pv from existing vg")

        self.parents.remove(pv)
        pv.removeChild()

    """ We can't rely on lvm to tell us about our size, free space, &c
        since we could have modifications queued, unless the VG and all of
        its PVs already exist.

            -- liblvm may contain support for in-memory devices
    """
    @property
    def isModified(self):
        """ Return True if the VG has changes queued that LVM is unaware of. """
        modified = True
        if self.exists and not filter(lambda d: not d.exists, self.pvs):
            modified = False

        return modified

    @property
    def size(self):
        """ The size of this VG """
        # TODO: just ask lvm if isModified returns False

        # sum up the sizes of the PVs and align to pesize
        size = 0
        for pv in self.pvs:
            size += self.align(pv.size - pv.format.peStart)

        return size

    @property
    def extents(self):
        """ Number of extents in this VG """
        # TODO: just ask lvm if isModified returns False

        return self.size / self.peSize

    @property
    def freeSpace(self):
        """ The amount of free space in this VG (in MB). """
        # TODO: just ask lvm if isModified returns False

        # total the sizes of any LVs
        used = 0
        size = self.size
        log.debug("%s size is %dMB" % (self.name, size))
        for lv in self.lvs:
            log.debug("lv %s (%s) uses %dMB" % (lv.name, lv, lv.size))
            used += self.align(lv.size)

        free = self.size - used
        log.debug("vg %s has %dMB free" % (self.name, free))
        return free

    @property
    def freeExtents(self):
        """ The number of free extents in this VG. """
        # TODO: just ask lvm if isModified returns False
        return self.freeSpace / self.peSize

    def align(self, size):
        """ Align a size to a multiple of physical extent size. """
        size = numeric_type(size)

        # we want Kbytes as a float for our math
        size *= 1024.0
        pesize = self.peSize * 1024.0
        return long((math.floor(size / pesize) * pesize) / 1024)

    @property
    def pvs(self):
        """ A list of this VG's PVs """
        return self.parents[:]  # we don't want folks changing our list

    @property
    def lvs(self):
        """ A list of this VG's LVs """
        return self._lvs[:]     # we don't want folks changing our list

    @property
    def complete(self):
        """Check if the vg has all its pvs in the system
        Return True if complete.
        """
        return len(self.pvs) == self.pvCount or not self.exists


class LVMLogicalVolumeDevice(DMDevice):
    """ An LVM Logical Volume """
    _type = "lvmlv"
    _resizable = True

    def __init__(self, name, vgdev, size=None, uuid=None,
                 format=None, exists=None, sysfsPath='',
                 grow=None, maxsize=None, percent=None):
        """ Create a LVMLogicalVolumeDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)
                vgdev -- volume group (LVMVolumeGroupDevice instance)

            Keyword Arguments:

                size -- the device's size (in MB)
                uuid -- the device's UUID
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                exists -- indicates whether this is an existing device

                For new (non-existent) LVs only:

                    grow -- whether to grow this LV
                    maxsize -- maximum size for growable LV (in MB)
                    percent -- percent of VG space to take

        """
        if isinstance(vgdev, list):
            if len(vgdev) != 1:
                raise ValueError("constructor requires a single LVMVolumeGroupDevice instance")
            elif not isinstance(vgdev[0], LVMVolumeGroupDevice):
                raise ValueError("constructor requires a LVMVolumeGroupDevice instance")
        elif not isinstance(vgdev, LVMVolumeGroupDevice):
            raise ValueError("constructor requires a LVMVolumeGroupDevice instance")
        DMDevice.__init__(self, name, size=size, format=format,
                          sysfsPath=sysfsPath, parents=vgdev,
                          exists=exists)

        self.uuid = uuid

        self.req_grow = None
        self.req_max_size = 0
        self.req_size = 0   
        self.req_percent = 0

        if not self.exists:
            self.req_grow = grow
            self.req_max_size = numeric_type(maxsize)
            # XXX should we enforce that req_size be pe-aligned?
            self.req_size = self._size
            self.req_percent = numeric_type(percent)

        # here we go with the circular references
        self.vg._addLogVol(self)

    def __str__(self):
        s = DMDevice.__str__(self)
        s += ("  VG device = %(vgdev)r  percent = %(percent)s" %
              {"vgdev": self.vg, "percent": self.req_percent})
        return s

    def probe(self):
        """ Probe for any missing information about this device.

            size
        """
        raise NotImplementedError("probe method not defined for StorageDevice")

    def _setSize(self, size):
        size = self.vg.align(numeric_type(size))
        log.debug("trying to set lv %s size to %dMB" % (self.name, size))
        if size <= (self.vg.freeSpace + self._size):
            self._size = size
            self.targetSize = size
        else:
            log.debug("failed to set size: %dMB short" % (size - (self.vg.freeSpace + self._size),))
            raise ValueError("not enough free space in volume group")

    size = property(lambda d: d._size, _setSize)

    @property
    def vg(self):
        """ This Logical Volume's Volume Group. """
        return self.parents[0]

    @property
    def name(self):
        """ This device's name. """
        return "%s-%s" % (self.vg.name, self._name)

    @property
    def lvname(self):
        """ The LV's name (not including VG name). """
        return self._name

    @property
    def complete(self):
        """ Test if vg exits and if it has all pvs. """
        return self.vg.complete

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            return

        self.vg.setup()
        lvm.lvactivate(self.vg.name, self._name)

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists and not recursive:
            raise DeviceError("device has not been created")

        if self.status and self.format.exists:
            self.format.teardown()

        if self.status:
            lvm.lvdeactivate(self.vg.name, self._name)

        if recursive:
            # It's likely that teardown of a VG will fail due to other
            # LVs being active (filesystems mounted, &c), so don't let
            # it bring everything down.
            try:
                self.vg.teardown(recursive=recursive)
            except Exception as e:
                log.debug("vg %s teardown failed; continuing" % self.vg.name)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        self.createParents()
        self.setupParents()

        # should we use --zero for safety's sake?
        lvm.lvcreate(self.vg.name, self._name, self.size)
        # FIXME set / update self.uuid here
        self.exists = True
        self.setup()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            self.format.destroy()

        self.teardown()
        lvm.lvremove(self.vg.name, self._name)
        self.exists = False

    def resize(self, intf=None):
        # XXX should we set up anything before doing this?
        # XXX resize format probably, right?
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        self.format.teardown()
        lvm.lvresize(self.vg.name, self._name, self.size)


class MDRaidArrayDevice(StorageDevice):
    """ An mdraid (Linux RAID) device.

        Since this is derived from StorageDevice, not PartitionDevice, it
        can be used to represent a partitionable device.
    """
    _type = "mdarray"

    def __init__(self, name, level=None, minor=None, size=None,
                 memberDevices=None, totalDevices=None, bitmap=False,
                 uuid=None, format=None, exists=None,
                 parents=None, sysfsPath=''):
        """ Create a MDRaidArrayDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                level -- the device's RAID level (a string, eg: '1' or 'raid1')
                parents -- list of member devices (StorageDevice instances)
                size -- the device's size (units/format TBD)
                uuid -- the device's UUID
                minor -- the device minor
                bitmap -- whether to use a bitmap (boolean)
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                exists -- indicates whether this is an existing device
        """
        StorageDevice.__init__(self, name, format=format, exists=exists,
                               minor=minor, size=size,
                               parents=parents, sysfsPath=sysfsPath)
        self.level = level
        self.uuid = uuid
        self._totalDevices = numeric_type(totalDevices)
        self._memberDevices = numeric_type(memberDevices)
        self.sysfsPath = "/devices/virtual/block/%s" % name

        """ FIXME: Bitmap is more complicated than this.

            It can be internal or external. External requires a filename.
        """
        self.bitmap = bitmap

        self.formatClass = get_device_format_class("mdmember")
        if not self.formatClass:
            raise DeviceError("cannot find class for 'mdmember'")

        #self.probe()

    @property
    def size(self):
        size = None
        for device in self.devices:
            if size is None or device.size < size:
                size = device.size
        return size

    def __str__(self):
        s = StorageDevice.__str__(self)
        s += ("  level = %(level)s  bitmap = %(bitmap)s  spares = %(spares)s\n"
              "  members = %(memberDevices)s\n"
              "  total devices = %(totalDevices)s" %
              {"level": self.level, "bitmap": self.bitmap, "spares": self.spares,
               "memberDevices": self.memberDevices, "totalDevices": self.totalDevices})
        return s

    @property
    def mdadmConfEntry(self):
        """ This array's mdadm.conf entry. """
        if not self.level or self.memberDevices is None or not self.uuid:
            raise DeviceError("array is not fully defined")

        fmt = "ARRAY level=%s num-devices=%d UUID=%s"
        return fmt % (self.level, self.memberDevices, self.uuid)

    @property
    def totalDevices(self):
        """ Total number of devices in the array, including spares. """
        count = len(self.parents)
        if not self.exists:
            count = self._totalDevices
        return count

    def _getMemberDevices(self):
        return self._memberDevices

    def _setMemberDevices(self, number):
        if not isinstance(number, int):
            raise ValueError("memberDevices is an integer")

        if number > self.totalDevices:
            raise ValueError("memberDevices cannot be greater than totalDevices")
        self._memberDevices = number

    memberDevices = property(_getMemberDevices, _setMemberDevices,
                             doc="number of member devices")

    def _getSpares(self):
        spares = 0
        if self.memberDevices is not None:
            if self.totalDevices is not None:
                spares = self.totalDevices - self.memberDevices
            else:
                spares = self.memberDevices
                self.totalDevices = self.memberDevices
        return spares

    def _setSpares(self, spares):
        # FIXME: this is too simple to be right
        if self.totalDevices > spares:
            self.memberDevices = self.totalDevices - spares

    spares = property(_getSpares, _setSpares)

    def probe(self):
        """ Probe for any missing information about this device.

            I'd like to avoid paying any attention to "Preferred Minor"
            as it seems problematic.
        """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        try:
            self.devices[0].setup()
        except Exception:
            return

        info = mdraid.mdexamine(self.devices[0].path)
        if self.level is None:
            self.level = info['level']
        if self.memberDevices is None:
            self.memberDevices = info['nrDisks']
        if self.totalDevices is None:
            self.totalDevices = info['totalDisks']
        if self.uuid is None:
            self.uuid = info['uuid']
        if self.minor is None:
            self.minor = info['mdMinor']

    @property
    def fstabSpec(self):
        return self.path

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            self.sysfsPath = "/devices/virtual/block/%s" % self.name
        else:
            self.sysfsPath = ''

    def _addDevice(self, device):
        """ Add a new member device to the array.

            XXX This is for use when probing devices, not for modification
                of arrays.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if not isinstance(device.format, self.formatClass):
            raise ValueError("invalid device format for mdraid member")

        if self.uuid and device.format.mdUuid != self.uuid:
            raise ValueError("cannot add member with non-matching UUID")

        if device in self.devices:
            raise ValueError("device is already a member of this array")

        # we added it, so now set up the relations
        self.devices.append(device)
        device.addChild()

        if self.status:
            device.setup()
            mdraid.mdadd(device.path)

    def _removeDevice(self, device):
        """ Remove a component device from the array.

            XXX This is for use by clearpart, not for reconfiguration.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)

        if device not in self.devices:
            raise ValueError("cannot remove non-member device from array")

        self.devices.remove(device)
        device.removeChild()

    @property
    def status(self):
        """ This device's status.

            For now, this should return a boolean:
                True    the device is open and ready for use
                False   the device is not open
        """
        # check the status in sysfs
        status = False
        if not self.exists:
            return status

        state_file = "/sys/%s/md/array_state" % self.sysfsPath
        if os.access(state_file, os.R_OK):
            state = open(state_file).read().strip()
            log.debug("%s state is %s" % (self.name, state))
            if state in ("clean", "active"):
                status = True

        return status

    @property
    def degraded(self):
        """ Return True if the array is running in degraded mode. """
        rc = False
        degraded_file = "/sys/%s/md/degraded" % self.sysfsPath
        if os.access(state_file, os.R_OK):
            val = open(state_file).read().strip()
            log.debug("%s degraded is %s" % (self.name, val))
            if val == "1":
                rc = True

        return rc

    @property
    def devices(self):
        """ Return a list of this array's member device instances. """
        return self.parents

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            return

        disks = []
        for member in self.devices:
            member.setup()
            disks.append(member.path)

        mdraid.mdactivate(self.path,
                          members=disks,
                          super_minor=self.minor,
                          uuid=self.uuid)

        udev_settle()

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists and not recursive:
            raise DeviceError("device has not been created")

        if self.status and self.format.exists:
            self.format.teardown()

        if self.status:
            mdraid.mddeactivate(self.path)

        if recursive:
            self.teardownParents(recursive=recursive)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        disks = [disk.path for disk in self.devices]
        self.createParents()
        self.setupParents()
        spares = len(self.devices) - self.memberDevices
        mdraid.mdcreate(self.path,
                        self.level,
                        disks,
                        spares)
        self.exists = True
        # the array is automatically activated upon creation, but...
        self.setup()
        udev_settle()

        # FIXME: we need to find our UUID now that the array exists

    @property
    def formatArgs(self):
        formatArgs = []
        if self.format.type == "ext2":
            if self.level == 5:
                formatArgs = ['-R',
                              'stride=%d' % ((self.memberDevices - 1) * 16)]
            elif self.level == 0:
                formatArgs = ['-R',
                              'stride=%d' % (self.memberDevices * 16)]

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            self.format.destroy()

        self.teardown()

        # The destruction of the formatting on the member devices does the
        # real work, but it isn't our place to do it from here.
        self.exists = False


class DMRaidArrayDevice(DiskDevice):
    """ A dmraid (device-mapper RAID) device """
    _type = "dm-raid array"
    _packages = ["dmraid"]
    _devDir = "/dev/mapper"

    def __init__(self, name, raidSet=None, level=None, format=None,
                 size=None, major=None, minor=None, parents=None,
                 sysfsPath='', initcb=None, initlabel=None):
        """ Create a DMRaidArrayDevice instance.

            Arguments:

                name -- the dmraid name also the device node's basename

            Keyword Arguments:

                raidSet -- the RaidSet object from block
                level -- the type of dmraid
                parents -- a list of the member devices
                sysfsPath -- sysfs device path
                size -- the device's size
                format -- a DeviceFormat instance

                initcb -- the call back to be used when initiating disk.
                initlabel -- whether to start with a fresh disklabel
        """
        if isinstance(parents, list):
            for parent in parents:
                if not parent.format or parent.format.type != "dmraidmember":
                    raise ValueError("parent devices must contain dmraidmember format")
        DiskDevice.__init__(self, name, format=format, size=size,
                            major=major, minor=minor, parents=parents,
                            sysfsPath=sysfsPath, initcb=initcb,
                            initlabel=initlabel)

        self.formatClass = get_device_format_class("dmraidmember")
        if not self.formatClass:
            raise DeviceError("cannot find class for 'dmraidmember'")


        self._raidSet = raidSet
        self._level = level

    @property
    def raidSet(self):
        return self._raidSet

    def _addDevice(self, device):
        """ Add a new member device to the array.

            XXX This is for use when probing devices, not for modification
                of arrays.
        """
        log_method_call(self, self.name, device=device.name, status=self.status)

        if not self.exists:
            raise DeviceError("device has not been created")

        if not isinstance(device.format, self.formatClass):
            raise ValueError("invalid device format for dmraid member")

        if device in self.members:
            raise ValueError("device is already a member of this array")

        # we added it, so now set up the relations
        self.devices.append(device)
        device.addChild()

    @property
    def members(self):
        return self.parents

    @property
    def devices(self):
        """ Return a list of this array's member device instances. """
        return self.parents

    def activate(self, mknod=True):
        self._raidSet.activate(mknod=mknod)

    def deactivate(self):
        self._raidSet.deactivate()

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            dm_node = dm.dm_node_from_name(self.name)
            path = os.path.join("/sys", self.sysfsBlockDir, dm_node)
            self.sysfsPath = os.path.realpath(path)[4:]
        else:
            self.sysfsPath = ''


class MultipathDevice(DMDevice):
    """ A multipath device """
    _type = "dm-multipath"
    _packages = ["device-mapper-multipath"]

    def __init__(self, name, format=None, size=None,
                 exists=None, parents=None, sysfsPath=''):
        """ Create a MultipathDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                sysfsPath -- sysfs device path
                size -- the device's size
                format -- a DeviceFormat instance
                parents -- a list of the backing devices (Device instances)
                exists -- indicates whether this is an existing device
        """
        DMDevice.__init__(self, name, format=format, size=size,
                          parents=parents, sysfsPath=sysfsPath,
                          exists=exists)

    def probe(self):
        """ Probe for any missing information about this device.

            size
        """
        raise NotImplementedError("probe method not defined for MultipathDevice")


class NoDevice(StorageDevice):
    """ A nodev device for nodev filesystems like tmpfs. """
    _type = "nodev"

    def __init__(self, format=None):
        """ Create a NoDevice instance.

            Arguments:

            Keyword Arguments:

                format -- a DeviceFormat instance
        """
        if format:
            name = format.type
        else:
            name = "nodev"

        StorageDevice.__init__(self, name, format=format)

    @property
    def path(self):
        """ Device node representing this device. """
        return self.name

    def probe(self):
        """ Probe for any missing information about this device. """
        log_method_call(self, self.name, status=self.status)

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)

    def teardown(self, recursive=False):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        self.setupParents()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)


class FileDevice(StorageDevice):
    """ A file on a filesystem.

        This exists because of swap files.
    """
    _type = "file"
    _devDir = ""

    def __init__(self, path, format=None, size=None,
                 exists=None, parents=None):
        """ Create a FileDevice instance.

            Arguments:

                path -- full path to the file

            Keyword Arguments:

                format -- a DeviceFormat instance
                size -- the file size (units TBD)
                parents -- a list of required devices (Device instances)
                exists -- indicates whether this is an existing device
        """
        StorageDevice.__init__(self, name, format=format, size=size,
                               exists=exists, parents=parents)

    def probe(self):
        """ Probe for any missing information about this device. """
        pass

    @property
    def fstabSpec(self):
        return self.path

    @property
    def path(self):
        path = self.name
        root = ""
        try:
            status = self.parents[0].format.status
        except AttributeError:
            status = False

        if status: 
            # this is the actual active mountpoint
            root = self.parents[0].format._mountpoint

        return os.path.normpath("%s/%s" % (root, path))

    def setup(self):
        StorageDevice.setup(self)
        if self.format and self.format.exists and not self.format.status:
            self.format.device = self.path

        for parent in self.parents:
            parent.format.setup()

    def teardown(self):
        StorageDevice.teardown(self)
        if self.format and self.format.exists and not self.format.status:
            self.format.device = self.path

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        # this only checks that parents exist
        self.createParents()
        self.setupParents()

        try:
            fd = os.open(self.path, os.O_RDWR)
        except OSError as e:
            raise DeviceError(e)

        try:
            buf = '\0' * 1024 * 1024 * self.size
            os.write(fd, buf)
        except (OSError, TypeError) as e:
            log.error("error writing out %s: %s" % (self.path, e))
        finally:
            os.close(fd)

        self.exists = True

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        if self.status:
            self.format.destroy()

        os.unlink(self.path)
        self.exists = False


class DirectoryDevice(FileDevice):
    """ A directory on a filesystem.

        This exists because of bind mounts.
    """
    _type = "directory"

    def create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        if self.exists:
            raise DeviceError("device already exists")

        self.createParents()
        self.setupParents()
        try:
            iutil.mkdirChain(self.path)
        except Exception, e:
            raise DeviceError, e

        self.exists = True

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        os.unlink(self.path)
        self.exists = False


class iScsiDiskDevice(DiskDevice, NetworkStorageDevice):
    """ An iSCSI disk. """
    _type = "iscsi"
    _packages = ["iscsi-initiator-utils"]

    def __init__(self, device, **kwargs):
        self.iscsi_name    = kwargs.pop("iscsi_name")
        self.iscsi_address = kwargs.pop("iscsi_address")
        self.iscsi_port    = int(kwargs.pop("iscsi_port"))
        DiskDevice.__init__(self, device, **kwargs)
        NetworkStorageDevice.__init__(self, self.iscsi_address)
        log.debug("created new iscsi disk %s %s:%d" % (self.iscsi_name, self.iscsi_address, self.iscsi_port))

class OpticalDevice(StorageDevice):
    """ An optical drive, eg: cdrom, dvd+r, &c.

        XXX Is this useful?
    """
    _type = "cdrom"

    def __init__(self, name, major=None, minor=None, exists=None,
                 format=None, parents=None, sysfsPath=''):
        StorageDevice.__init__(self, name, format=format,
                               major=major, minor=minor, exists=True,
                               parents=parents, sysfsPath=sysfsPath)

    @property
    def mediaPresent(self):
        """ Return a boolean indicating whether or not the device contains
            media.
        """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        try:
            fd = os.open(self.path, os.O_RDONLY)
        except OSError as e:
            # errno 123 = No medium found
            if e.errno == 123:
                return False
            else:
                return True
        else:
            os.close(fd)
            return True

    def eject(self):
        """ Eject the drawer. """
        import _isys

        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created")

        # Make a best effort attempt to do the eject.  If it fails, it's not
        # critical.
        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)

        try:
            _isys.ejectcdrom(fd)
        except SystemError as e:
            log.warning("error ejecting cdrom %s: %s" % (device, e))

        os.close(fd)


class ZFCPDiskDevice(DiskDevice):
    """ A mainframe ZFCP disk. """
    _type = "zfcp"

    def __init__(self, name, size=None, major=None, minor=None,
                 devnum=None, wwpn=None, fcplun=None,
                 parents=None, sysfsPath=''):
        self.devnum = devnum
        self.wwpn = wwpn
        self.fcplun = fcplun
        name = "zfcp://%s/%s/%s" % (self.devnum, self.wwpn, self.fcplun)
        DiskDevice.__init__(self, name, size=size,
                            major=major, minor=minor,
                            parents=parents, sysfsPath=sysfsPath)

    def __str__(self):
        s = DiskDevice.__str__(self)
        s += ("  devnum = %(devnum)s  wwpn = %(wwpn)s  fcplun = %(fcplun)s" %
              {"devnum": self.devnum, "wwpn": self.wwpn, "fcplun": self.fcplun})
        return s

    def probe(self):
        """ Probe for any missing information about this device.

            devnum, wwpn, fcplun
        """
        raise NotImplementedError("probe method not defined for StorageDevice")


class DASDDevice(DiskDevice):
    """ A mainframe DASD. """
    _type = "dasd"

    def __init__(self, device, size=None, major=None, minor=None,
                 parents=None, sysfsPath=''):
        DiskDevice.__init__(self, device, size=size,
                            major=major, minor=minor,
                            parents=parents, sysfsPath=sysfsPath)

    def probe(self):
        """ Probe for any missing information about this device. """
        raise NotImplementedError("probe method not defined for StorageDevice")


class PRePBootDevice(PartitionDevice):
    """ A PPC PReP boot partition.

        XXX Would this be better represented by a DeviceFormat class?
    """
    _type = "PReP"
    #_partedFlags = parted.PARTITION_PREP

    def __init__(self, device,
                 size=None, grow=False, maxsize=None,
                 major=None, minor=None,
                 sysfsPath='', parents=None,
                 exists=None, primary=False):
        """ Create a PRePBootDevice instance.

            Arguments:

                device -- the device name (generally a device node's basename)

            Keyword Arguments:

                grow -- whether or not to grow the partition (boolean )
                maxsize -- max size for growable partitions (units TBD)
                size -- the device's size (units/format TBD)
                major -- the device major
                minor -- the device minor
                sysfsPath -- sysfs device path
                parents -- a list of required Device instances
                exists -- indicates whether this is an existing device
        """
        PartitionDevice.__init__(self, device, partType=self._partType,
                                 size=size, grow=grow, maxsize=maxsize,
                                 major=major, minor=minor,
                                 sysfsPath=sysfsPath, exists=exists,
                                 parents=parents, primary=primary)


class NFSDevice(StorageDevice, NetworkStorageDevice):
    """ An NFS device """
    _type = "nfs"

    def __init__(self, device, format=None, parents=None):
        # we could make host/ip, path, &c but will anything use it?
        StorageDevice.__init__(self, device, format=format, parents=parents)
        NetworkStorageDevice.__init__(self, device.split(":")[0])

    @property
    def path(self):
        """ Device node representing this device. """
        return self.name

    def setup(self, intf=None):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, status=self.status)

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status)

    def create(self, intf=None):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        self.createParents()
        self.setupParents()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)


