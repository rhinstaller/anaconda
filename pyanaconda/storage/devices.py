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
import pprint
import tempfile

# device backend modules
from devicelibs import mdraid
from devicelibs import lvm
from devicelibs import dm
from devicelibs import loop
from devicelibs import btrfs
from devicelibs import crypto
import parted
import _ped
import block

from errors import *
from pyanaconda.iutil import notify_kernel, numeric_type
from pyanaconda.flags import flags
from pyanaconda.anaconda_log import log_method_call
from udev import *
from formats import get_device_format_class, getFormat, DeviceFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

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


def devicePathToName(devicePath):
    if devicePath.startswith("/dev/"):
        name = devicePath[5:]
    else:
        name = devicePath

    if name.startswith("mapper/"):
        name = name[7:]

    if name.startswith("md/"):
        name = name[3:]

    return name


def deviceNameToDiskByPath(deviceName=None):
    if not deviceName:
        return ""

    ret = None
    for dev in udev_get_block_devices():
        if udev_device_get_name(dev) == deviceName:
            ret = udev_device_get_by_path(dev)
            break

    if ret:
        return ret
    raise DeviceNotFoundError(deviceName)

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

    # This is a counter for generating unique ids for Devices.
    _id = 0

    _type = "device"
    _packages = []
    _services = []

    def __init__(self, name, parents=None):
        """ Create a Device instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                parents -- a list of required Device instances

        """
        self._name = name
        if parents is None:
            parents = []
        elif not isinstance(parents, list):
            raise ValueError("parents must be a list of Device instances")
        self.parents = parents
        self.kids = 0

        # Set this instance's id and increment the counter.
        self.id = Device._id
        Device._id += 1

        for parent in self.parents:
            parent.addChild()

    def __deepcopy__(self, memo):
        """ Create a deep copy of a Device instance.

            We can't do copy.deepcopy on parted objects, which is okay.
            For these parted objects, we just do a shallow copy.
        """
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        dont_copy_attrs = ('_raidSet',)
        shallow_copy_attrs = ('_partedDevice', '_partedPartition')
        for (attr, value) in self.__dict__.items():
            if attr in dont_copy_attrs:
                setattr(new, attr, value)
            elif attr in shallow_copy_attrs:
                setattr(new, attr, copy.copy(value))
            else:
                setattr(new, attr, copy.deepcopy(value, memo))

        return new

    def __repr__(self):
        s = ("%(type)s instance (%(id)s) --\n"
             "  name = %(name)s  status = %(status)s"
             "  kids = %(kids)s id = %(dev_id)s\n"
             "  parents = %(parents)s\n" %
             {"type": self.__class__.__name__, "id": "%#x" % id(self),
              "name": self.name, "kids": self.kids, "status": self.status,
              "dev_id": self.id,
              "parents": pprint.pformat([str(p) for p in self.parents])})
        return s

    def __str__(self):
        s = "%s %s (%d)" % (self.type, self.name, self.id)
        return s

    @property
    def dict(self):
        d =  {"type": self.type, "name": self.name,
              "parents": [p.name for p in self.parents]}
        return d

    def removeChild(self):
        log_method_call(self, name=self.name, kids=self.kids)
        self.kids -= 1

    def addChild(self):
        log_method_call(self, name=self.name, kids=self.kids)
        self.kids += 1

    def setup(self):
        """ Open, or set up, a device. """
        raise NotImplementedError("setup method not defined for Device")

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        raise NotImplementedError("teardown method not defined for Device")

    def create(self):
        """ Create the device. """
        raise NotImplementedError("create method not defined for Device")

    def destroy(self):
        """ Destroy the device. """
        raise NotImplementedError("destroy method not defined for Device")

    def setupParents(self, orig=False):
        """ Run setup method of all parent devices. """
        log_method_call(self, name=self.name, orig=orig, kids=self.kids)
        for parent in self.parents:
            parent.setup(orig=orig)

    def teardownParents(self, recursive=None):
        """ Run teardown method of all parent devices. """
        for parent in self.parents:
            parent.teardown(recursive=recursive)

    def dependsOn(self, dep):
        """ Return True if this device depends on dep. """
        # XXX does a device depend on itself?
        if dep in self.parents:
            return True

        for parent in self.parents:
            if parent.dependsOn(dep):
                return True

        return False

    def dracutSetupArgs(self):
        return set()

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
    def ancestors(self):
        l = set([self])
        for p in [d for d in self.parents if d not in l]:
            l.update(set(p.ancestors))
        return list(l)

    @property
    def packages(self):
        """ List of packages required to manage devices of this type.

            This list includes the packages required by its parent devices.
        """
        packages = self._packages
        for parent in self.parents:
            for package in parent.packages:
                if package not in packages:
                    packages.append(package)

        return packages

    @property
    def services(self):
        """ List of services required to manage devices of this type.

            This list includes the services required by its parent devices."
        """
        services = self._services
        for parent in self.parents:
            for service in parent.services:
                if service not in services:
                    services.append(service)

        return services

    @property
    def mediaPresent(self):
        return True


class NetworkStorageDevice(object):
    """ Virtual base class for network backed storage devices """

    def __init__(self, host_address=None, nic=None):
        """ Create a NetworkStorage Device instance. Note this class is only
            to be used as a baseclass and then only with multiple inheritance.
            The only correct use is:
            class MyStorageDevice(StorageDevice, NetworkStorageDevice):

            The sole purpose of this class is to:
            1) Be able to check if a StorageDevice is network backed
               (using isinstance).
            2) To be able to get the host address of the host (server) backing
               the storage *or* the NIC through which the storage is connected

            Arguments:

                host_address -- host address of the backing server
                nic -- nic to which the storage is bound
        """
        self.host_address = host_address
        self.nic = nic


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
    _type = "storage"
    _devDir = "/dev"
    sysfsBlockDir = "class/block"
    _resizable = False
    _partitionable = False
    _isDisk = False

    def __init__(self, name, format=None, uuid=None,
                 size=None, major=None, minor=None,
                 sysfsPath='', parents=None, exists=False, serial=None,
                 vendor="", model="", bus=""):
        """ Create a StorageDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                major -- the device major
                minor -- the device minor
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                uuid -- universally unique identifier
                parents -- a list of required Device instances
                serial -- the ID_SERIAL_SHORT for this device
                vendor -- the manufacturer of this Device
                model -- manufacturer's device model string
                bus -- the interconnect this device uses

        """
        # allow specification of individual parents
        if isinstance(parents, Device):
            parents = [parents]

        self.exists = exists
        Device.__init__(self, name, parents=parents)

        self.uuid = uuid
        self._format = None
        self._size = numeric_type(size)
        self.major = numeric_type(major)
        self.minor = numeric_type(minor)
        self.sysfsPath = sysfsPath
        self._serial = serial
        self._vendor = vendor
        self._model = model
        self.bus = bus

        self.protected = False
        self.controllable = not flags.testing

        self.format = format
        self.originalFormat = copy.copy(self.format)
        self.fstabComment = ""
        self._targetSize = self._size

        self._partedDevice = None

        if self.exists and flags.testing and not self._size:
            def read_int_from_sys(path):
                return int(open(path).readline().strip())

            device_root = "/sys/class/block/%s" % self.name
            if os.path.exists("%s/queue" % device_root):
                sector_size = read_int_from_sys("%s/queue/logical_block_size"
                                                % device_root)
                size = read_int_from_sys("%s/size" % device_root)
                self._size = (size * sector_size) / (1024.0 * 1024.0)

    def __str__(self):
        exist = "existing"
        if not self.exists:
            exist = "non-existent"
        s = "%s %dMB %s" % (exist, self.size, super(StorageDevice, self).__str__())
        if self.format.type:
            s += " with %s" % self.format

        return s

    @property
    def packages(self):
        """ List of packages required to manage devices of this type.

            This list includes the packages required by this device's
            format type as well those required by all of its parent 
            devices.
        """
        packages = super(StorageDevice, self).packages
        packages.extend(self.format.packages)
        for parent in self.parents:
            for package in parent.format.packages:
                if package not in packages:
                    packages.append(package)

        return packages

    @property
    def services(self):
        """ List of services required to manage devices of this type.

            This list includes the services required by this device's
            format type as well those required by all of its parent
            devices.
        """
        services = super(StorageDevice, self).services
        services.extend(self.format.services)
        for parent in self.parents:
            for service in parent.format.services:
                if service not in services:
                    services.append(service)

        return services

    @property
    def disks(self):
        """ A list of all disks this device depends on, including itself. """
        _disks = []
        for parent in self.parents:
            for disk in parent.disks:
                if disk not in _disks:
                    _disks.append(disk)

        if self.isDisk and not self.format.hidden:
            _disks.append(self)

        return _disks

    @property
    def encrypted(self):
        """ True if this device, or any it requires, is encrypted. """
        crypted = False
        for parent in self.parents:
            if parent.encrypted:
                crypted = True
                break

        if not crypted and isinstance(self, DMCryptDevice):
            crypted = True

        return crypted

    @property
    def partedDevice(self):
        if self.exists and self.status and not self._partedDevice:
            log.debug("looking up parted Device: %s" % self.path)

            # We aren't guaranteed to be able to get a device.  In
            # particular, built-in USB flash readers show up as devices but
            # do not always have any media present, so parted won't be able
            # to find a device.
            try:
                self._partedDevice = parted.Device(path=self.path)
            except (_ped.IOException, _ped.DeviceException):
                pass

        return self._partedDevice

    def _getTargetSize(self):
        return self._targetSize

    def _setTargetSize(self, newsize):
        self._targetSize = newsize

    targetSize = property(lambda s: s._getTargetSize(),
                          lambda s, v: s._setTargetSize(v),
                          doc="Target size of this device")

    def __repr__(self):
        s = Device.__repr__(self)
        s += ("  uuid = %(uuid)s  size = %(size)s\n"
              "  format = %(format)s\n"
              "  major = %(major)s  minor = %(minor)s  exists = %(exists)s"
              "  protected = %(protected)s\n"
              "  sysfs path = %(sysfs)s  partedDevice = %(partedDevice)s\n"
              "  target size = %(targetSize)s  path = %(path)s\n"
              "  format args = %(formatArgs)s  originalFormat = %(origFmt)s" %
              {"uuid": self.uuid, "format": self.format, "size": self.size,
               "major": self.major, "minor": self.minor, "exists": self.exists,
               "sysfs": self.sysfsPath, "partedDevice": self.partedDevice,
               "targetSize": self.targetSize, "path": self.path,
               "protected": self.protected,
               "formatArgs": self.formatArgs, "origFmt": self.originalFormat.type})
        return s

    @property
    def dict(self):
        d =  super(StorageDevice, self).dict
        d.update({"uuid": self.uuid, "size": self.size,
                  "format": self.format.dict, "removable": self.removable,
                  "major": self.major, "minor": self.minor,
                  "exists": self.exists, "sysfs": self.sysfsPath,
                  "targetSize": self.targetSize, "path": self.path})
        return d

    @property
    def path(self):
        """ Device node representing this device. """
        return "%s/%s" % (self._devDir, self.name)

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        sysfsName = self.name.replace("/", "!")
        path = os.path.join("/sys", self.sysfsBlockDir, sysfsName)
        self.sysfsPath = os.path.realpath(path)[4:]
        log.debug("%s sysfsPath set to %s" % (self.name, self.sysfsPath))

    @property
    def formatArgs(self):
        """ Device-specific arguments to format creation program. """
        return []

    @property
    def resizable(self):
        """ Can this type of device be resized? """
        return (self._resizable and self.exists and self.format.resizable)

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
        except (ValueError, IOError) as e:
            log.warning("failed to notify kernel of change: %s" % e)

    @property
    def fstabSpec(self):
        spec = self.path
        if self.format and self.format.uuid:
            spec = "UUID=%s" % self.format.uuid
        return spec

    def resize(self):
        """ Resize the device.

            New size should already be set.
        """
        raise NotImplementedError("resize method not defined for StorageDevice")

    #
    # setup
    #
    def _preSetup(self, orig=False):
        """ Preparation and pre-condition checking for device setup.

            Return True if setup should proceed or False if not.
        """
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        if self.status or not self.controllable:
            return False

        self.setupParents(orig=orig)
        return True

    def _setup(self, orig=False):
        """ Perform device-specific setup operations. """
        pass

    def setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        if not self._preSetup(orig=orig):
            return

        self._setup(orig=orig)
        self._postSetup()

    def _postSetup(self):
        """ Perform post-setup operations. """
        udev_settle()
        # we always probe since the device may not be set up when we want
        # information about it
        self._size = self.currentSize

    #
    # teardown
    #
    def _preTeardown(self, recursive=None):
        """ Preparation and pre-condition checking for device teardown.

            Return True if teardown should proceed or False if not.
        """
        if not self.exists and not recursive:
            raise DeviceError("device has not been created", self.name)

        if not self.status or not self.controllable:
            return False

        if self.originalFormat.exists:
            self.originalFormat.teardown()
        self.format.cacheMajorminor()
        if self.format.exists:
            self.format.teardown()
        udev_settle()
        return True

    def _teardown(self, recursive=None):
        """ Perform device-specific teardown operations. """
        pass

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        if not self._preTeardown(recursive=recursive):
            return

        self._teardown(recursive=recursive)
        self._postTeardown(recursive=recursive)

    def _postTeardown(self, recursive=None):
        """ Perform post-teardown operations. """
        if recursive:
            self.teardownParents(recursive=recursive)

    #
    # create
    #
    def _preCreate(self):
        """ Preparation and pre-condition checking for device creation. """
        if self.exists:
            raise DeviceError("device has already been created", self.name)

        self.setupParents()

    def _create(self):
        """ Perform device-specific create operations. """
        pass

    def create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        self._preCreate()
        try:
            self._create()
        except Exception as e:
            raise DeviceCreateError(str(e), self.name)
        else:
            self._postCreate()

    def _postCreate(self):
        """ Perform post-create operations. """
        self.exists = True
        self.setup()
        self.updateSysfsPath()
        udev_settle()

    #
    # destroy
    #
    def _preDestroy(self):
        """ Preparation and precondition checking for device destruction. """
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        if not self.isleaf:
            raise DeviceError("Cannot destroy non-leaf device", self.name)

        self.teardown()

    def _destroy(self):
        """ Perform device-specific destruction operations. """
        pass

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        self._preDestroy()
        self._destroy()
        self._postDestroy()

    def _postDestroy(self):
        """ Perform post-destruction operations. """
        self.exists = False

    def setupParents(self, orig=False):
        """ Run setup method of all parent devices. """
        log_method_call(self, name=self.name, orig=orig, kids=self.kids)
        for parent in self.parents:
            parent.setup(orig=orig)
            if orig:
                _format = parent.originalFormat
            else:
                _format = parent.format

            # set up the formatting, if present
            if _format.type and _format.exists:
                _format.setup()

    def _getSize(self):
        """ Get the device's size in MB, accounting for pending changes. """
        if self.exists and not self.mediaPresent:
            return 0

        if self.exists and self.partedDevice:
            self._size = self.currentSize

        size = self._size
        if self.exists and self.resizable and self.targetSize != size:
            size = self.targetSize

        return size

    def _setSize(self, newsize):
        """ Set the device's size to a new value. """
        if newsize > self.maxSize:
            raise DeviceError("device cannot be larger than %s MB" %
                              (self.maxSize,), self.name)
        self._size = newsize

    size = property(lambda x: x._getSize(),
                    lambda x, y: x._setSize(y),
                    doc="The device's size in MB, accounting for pending changes")

    @property
    def currentSize(self):
        """ The device's actual size. """
        size = 0
        if self.exists and self.partedDevice:
            size = self.partedDevice.getSize()
        elif self.exists:
            size = self._size
        return size

    @property
    def minSize(self):
        """ The minimum size this device can be. """
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
            raise DeviceError("cannot replace active format", self.name)

        self._format = format
        self._format.device = self.path

    def _getFormat(self):
        return self._format

    format = property(lambda d: d._getFormat(),
                      lambda d,f: d._setFormat(f),
                      doc="The device's formatting.")

    def preCommitFixup(self, *args, **kwargs):
        """ Do any necessary pre-commit fixups."""
        pass

    @property
    def removable(self):
        devpath = os.path.normpath("/sys/%s" % self.sysfsPath)
        remfile = os.path.normpath("%s/removable" % devpath)
        return (self.sysfsPath and os.path.exists(devpath) and
                os.access(remfile, os.R_OK) and
                open(remfile).readline().strip() == "1")

    @property
    def isDisk(self):
        return self._isDisk

    @property
    def partitionable(self):
        return self._partitionable

    @property
    def partitioned(self):
        return self.format.type == "disklabel" and self.partitionable

    @property
    def serial(self):
        return self._serial

    @property
    def model(self):
        if not self._model:
            self._model = getattr(self.partedDevice, "model", "")
        return self._model

    @property
    def vendor(self):
        return self._vendor

    @property
    def growable(self):
        """ True if this device or it's component devices are growable. """
        grow = getattr(self, "req_grow", False)
        if not grow:
            for parent in self.parents:
                grow = parent.growable
                if grow:
                    break
        return grow

    def checkSize(self):
        """ Check to make sure the size of the device is allowed by the
            format used.

            Returns:
            0  - ok
            1  - Too large
            -1 - Too small
        """
        if self.format.maxSize and self.size > self.format.maxSize:
            return 1
        elif self.format.minSize and self.size < self.format.minSize:
            return -1
        return 0

class DiskDevice(StorageDevice):
    """ A disk """
    _type = "disk"
    _partitionable = True
    _isDisk = True

    def __init__(self, name, format=None,
                 size=None, major=None, minor=None, sysfsPath='',
                 parents=None, serial=None, vendor="", model="", bus="",
                 exists=True):
        """ Create a DiskDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                major -- the device major
                minor -- the device minor
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                removable -- whether or not this is a removable device
                serial -- the ID_SERIAL_SHORT for this device
                vendor -- the manufacturer of this Device
                model -- manufacturer's device model string
                bus -- the interconnect this device uses


            DiskDevices always exist.
        """
        StorageDevice.__init__(self, name, format=format, size=size,
                               major=major, minor=minor, exists=exists,
                               sysfsPath=sysfsPath, parents=parents,
                               serial=serial, model=model,
                               vendor=vendor, bus=bus)

    def __repr__(self):
        s = StorageDevice.__repr__(self)
        s += ("  removable = %(removable)s  partedDevice = %(partedDevice)r" %
              {"removable": self.removable, "partedDevice": self.partedDevice})
        return s

    @property
    def mediaPresent(self):
        if flags.testing:
            return True

        if not self.partedDevice:
            return False

        # Some drivers (cpqarray <blegh>) make block device nodes for
        # controllers with no disks attached and then report a 0 size,
        # treat this as no media present
        return self.partedDevice.getSize() != 0

    @property
    def description(self):
        return self.model

    @property
    def size(self):
        """ The disk's size in MB """
        return super(DiskDevice, self).size
    #size = property(StorageDevice._getSize)

    def _preDestroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.mediaPresent:
            raise DeviceError("cannot destroy disk with no media", self.name)

        StorageDevice._preDestroy(self)


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
    defaultSize = 500

    def __init__(self, name, format=None,
                 size=None, grow=False, maxsize=None,
                 major=None, minor=None, bootable=None,
                 sysfsPath='', parents=None, exists=False,
                 partType=None, primary=False, weight=0):
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
                    weight -- an initial sorting weight to assign
        """
        self.req_disks = []
        self.req_partType = None
        self.req_primary = None
        self.req_grow = None
        self.req_bootable = None
        self.req_size = 0
        self.req_base_size = 0
        self.req_max_size = 0
        self.req_base_weight = 0

        self._bootable = False

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
        self._origPath = None
        self._currentSize = 0

        # FIXME: Validate size, but only if this is a new partition.
        #        For existing partitions we will get the size from
        #        parted.

        if self.exists and not flags.testing:
            log.debug("looking up parted Partition: %s" % self.path)
            self._partedPartition = self.disk.format.partedDisk.getPartitionByPath(self.path)
            if not self._partedPartition:
                raise DeviceError("cannot find parted partition instance", self.name)

            self._origPath = self.path
            # collect information about the partition from parted
            self.probe()
            if self.getFlag(parted.PARTITION_PREP):
                # the only way to identify a PPC PReP Boot partition is to
                # check the partition type/flags, so do it here.
                self.format = getFormat("prepboot", device=self.path, exists=True)
            elif self.getFlag(parted.PARTITION_BIOS_GRUB):
                # the only way to identify a BIOS Boot partition is to
                # check the partition type/flags, so do it here.
                self.format = getFormat("biosboot", device=self.path, exists=True)
        else:
            # XXX It might be worthwhile to create a shit-simple
            #     PartitionRequest class and pass one to this constructor
            #     for new partitions.
            if not self._size:
                # default size for new partition requests
                self._size = self.defaultSize
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

            self.req_base_weight = weight

    def __repr__(self):
        s = StorageDevice.__repr__(self)
        s += ("  grow = %(grow)s  max size = %(maxsize)s  bootable = %(bootable)s\n"
              "  part type = %(partType)s  primary = %(primary)s\n"
              "  partedPartition = %(partedPart)s\n"
              "  disk = %(disk)s\n" %
              {"grow": self.req_grow, "maxsize": self.req_max_size,
               "bootable": self.bootable, "partType": self.partType,
               "primary": self.req_primary,
               "partedPart": self.partedPartition, "disk": self.disk})

        if self.partedPartition:
            s += ("  start = %(start)s  end = %(end)s  length = %(length)s\n"
                  "  flags = %(flags)s" %
                  {"length": self.partedPartition.geometry.length,
                   "start": self.partedPartition.geometry.start,
                   "end": self.partedPartition.geometry.end,
                   "flags": self.partedPartition.getFlagsAsString()})

        return s

    @property
    def dict(self):
        d = super(PartitionDevice, self).dict
        d.update({"type": self.partType})
        if not self.exists:
            d.update({"grow": self.req_grow, "maxsize": self.req_max_size,
                      "bootable": self.bootable,
                      "primary": self.req_primary})

        if self.partedPartition:
            d.update({"length": self.partedPartition.geometry.length,
                      "start": self.partedPartition.geometry.start,
                      "end": self.partedPartition.geometry.end,
                      "flags": self.partedPartition.getFlagsAsString()})
        return d

    def _setTargetSize(self, newsize):
        if newsize != self.currentSize:
            # change this partition's geometry in-memory so that other
            # partitioning operations can complete (e.g., autopart)
            self._targetSize = newsize
            disk = self.disk.format.partedDisk

            # resize the partition's geometry in memory
            (constraint, geometry) = self._computeResize(self.partedPartition)
            disk.setPartitionGeometry(partition=self.partedPartition,
                                      constraint=constraint,
                                      start=geometry.start, end=geometry.end)

    @property
    def path(self):
        if not self.parents:
            devDir = StorageDevice._devDir
        else:
            devDir = self.parents[0]._devDir

        return "%s/%s" % (devDir, self.name)

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
        return (self.partType is not None and
                self.partType & parted.PARTITION_EXTENDED)

    @property
    def isLogical(self):
        return (self.partType is not None and
                self.partType & parted.PARTITION_LOGICAL)

    @property
    def isPrimary(self):
        return (self.partType is not None and
                self.partType == parted.PARTITION_NORMAL)

    @property
    def isProtected(self):
        return (self.partType is not None and
                self.partType & parted.PARTITION_PROTECTED)

    @property
    def fstabSpec(self):
        spec = self.path
        if self.disk and self.disk.type == 'dasd':
            spec = deviceNameToDiskByPath(self.name)
        elif self.format and self.format.uuid:
            spec = "UUID=%s" % self.format.uuid
        return spec

    def _getPartedPartition(self):
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

        log.debug("device %s new partedPartition %s" % (self.name, partition))
        self._partedPartition = partition
        self.updateName()

    partedPartition = property(lambda d: d._getPartedPartition(),
                               lambda d,p: d._setPartedPartition(p))

    def preCommitFixup(self, *args, **kwargs):
        """ Re-get self.partedPartition from the original disklabel. """
        log_method_call(self, self.name)
        if not self.exists:
            return

        # find the correct partition on the original parted.Disk since the
        # name/number we're now using may no longer match
        _disklabel = self.disk.originalFormat

        if self.isExtended:
            # getPartitionBySector doesn't work on extended partitions
            _partition = _disklabel.extendedPartition
            log.debug("extended lookup found partition %s"
                        % devicePathToName(getattr(_partition, "path", None)))
        else:
            # lookup the partition by sector to avoid the renumbering
            # nonsense entirely
            _sector = self.partedPartition.geometry.start
            _partition = _disklabel.partedDisk.getPartitionBySector(_sector)
            log.debug("sector-based lookup found partition %s"
                        % devicePathToName(getattr(_partition, "path", None)))

        self.partedPartition = _partition

    def _getWeight(self):
        return self.req_base_weight

    def _setWeight(self, weight):
        self.req_base_weight = weight

    weight = property(lambda d: d._getWeight(),
                      lambda d,w: d._setWeight(w))

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.parents:
            self.sysfsPath = ''

        elif isinstance(self.parents[0], DMDevice):
            dm_node = dm.dm_node_from_name(self.name)
            path = os.path.join("/sys", self.sysfsBlockDir, dm_node)
            self.sysfsPath = os.path.realpath(path)[4:]
        elif isinstance(self.parents[0], MDRaidArrayDevice):
            md_node = mdraid.md_node_from_name(self.name)
            path = os.path.join("/sys", self.sysfsBlockDir, md_node)
            self.sysfsPath = os.path.realpath(path)[4:]
        else:
            StorageDevice.updateSysfsPath(self)

    def updateName(self):
        if self.partedPartition is None:
            self._name = self.req_name
        else:
            self._name = \
                devicePathToName(self.partedPartition.getDeviceNodeName())

    def dependsOn(self, dep):
        """ Return True if this device depends on dep. """
        if isinstance(dep, PartitionDevice) and dep.isExtended and \
           self.isLogical and self.disk == dep.disk:
            return True

        return Device.dependsOn(self, dep)

    def _setFormat(self, format):
        """ Set the Device's format. """
        log_method_call(self, self.name)
        StorageDevice._setFormat(self, format)

    def _setBootable(self, bootable):
        """ Set the bootable flag for this partition. """
        if self.partedPartition:
            if iutil.isS390():
                return
            if self.flagAvailable(parted.PARTITION_BOOT):
                if bootable:
                    self.setFlag(parted.PARTITION_BOOT)
                else:
                    self.unsetFlag(parted.PARTITION_BOOT)
            else:
                raise DeviceError("boot flag not available for this partition", self.name)

            self._bootable = bootable
        else:
            self.req_bootable = bootable

    def _getBootable(self):
        return self._bootable or self.req_bootable

    bootable = property(_getBootable, _setBootable)

    def flagAvailable(self, flag):
        if not self.partedPartition:
            return

        return self.partedPartition.isFlagAvailable(flag)

    def getFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        return self.partedPartition.getFlag(flag)

    def setFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        self.partedPartition.setFlag(flag)

    def unsetFlag(self, flag):
        log_method_call(self, path=self.path, flag=flag)
        if not self.partedPartition or not self.flagAvailable(flag):
            return

        self.partedPartition.unsetFlag(flag)

    @property
    def isMagic(self):
        if not self.disk:
            return False

        number = getattr(self.partedPartition, "number", -1)
        magic = self.disk.format.magicPartitionNumber
        return (number == magic)

    def probe(self):
        """ Probe for any missing information about this device.

            size, partition type, flags
        """
        log_method_call(self, self.name, exists=self.exists)
        if not self.exists:
            return

        # this is in MB
        self._size = self.partedPartition.getSize()
        self._currentSize = self._size
        self.targetSize = self._size

        self._partType = self.partedPartition.type

        self._bootable = self.getFlag(parted.PARTITION_BOOT)

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        self.disk.format.addPartition(self.partedPartition)

        try:
            self.disk.format.commit()
        except DiskLabelCommitError:
            part = self.disk.format.partedDisk.getPartitionByPath(self.path)
            self.disk.format.removePartition(part)
            raise

    def _postCreate(self):
        if self.isExtended:
            partition = self.disk.format.extendedPartition
        else:
            start = self.partedPartition.geometry.start
            partition = self.disk.format.partedDisk.getPartitionBySector(start)

        log.debug("post-commit partition path is %s" % getattr(partition,
                                                               "path", None))
        self.partedPartition = partition
        if not self.isExtended:
            # Ensure old metadata which lived in freespace so did not get
            # explictly destroyed by a destroyformat action gets wiped
            DeviceFormat(device=self.path, exists=True).destroy()

        StorageDevice._postCreate(self)
        self._currentSize = self.partedPartition.getSize()

    def _computeResize(self, partition):
        log_method_call(self, self.name, status=self.status)

        # compute new size for partition
        currentGeom = partition.geometry
        currentDev = currentGeom.device
        newLen = long(self.targetSize * 1024 * 1024) / currentDev.sectorSize
        newGeometry = parted.Geometry(device=currentDev,
                                      start=currentGeom.start,
                                      length=newLen)
        # and align the end sector
        newGeometry.end = self.disk.format.endAlignment.alignDown(newGeometry,
                                                               newGeometry.end)
        constraint = parted.Constraint(exactGeom=newGeometry)

        return (constraint, newGeometry)

    def resize(self):
        """ Resize the device.

            self.targetSize must be set to the new size.
        """
        log_method_call(self, self.name, status=self.status)
        self._preDestroy()
        if self.targetSize != self.currentSize:
            # partedDisk has been restored to _origPartedDisk, so
            # recalculate resize geometry because we may have new
            # partitions on the disk, which could change constraints
            partedDisk = self.disk.format.partedDisk
            partition = partedDisk.getPartitionByPath(self.path)
            (constraint, geometry) = self._computeResize(partition)

            partedDisk.setPartitionGeometry(partition=partition,
                                            constraint=constraint,
                                            start=geometry.start,
                                            end=geometry.end)

            self.disk.format.commit()
            self._currentSize = partition.getSize()

    def _preDestroy(self):
        StorageDevice._preDestroy(self)
        if not self.sysfsPath:
            return

        self.setupParents(orig=True)

    def _destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        # we should have already set self.partedPartition to point to the
        # partition on the original disklabel
        self.disk.originalFormat.removePartition(self.partedPartition)
        try:
            self.disk.originalFormat.commit()
        except DiskLabelCommitError:
            self.disk.originalFormat.addPartition(self.partedPartition)
            self.partedPartition = self.disk.originalFormat.partedDisk.getPartitionByPath(self.path)
            raise

        if self.disk.format.exists and \
           self.disk.format.partedDisk != self.disk.originalFormat.partedDisk:
            # If the new/current disklabel is the same as the original one, we
            # have to duplicate the removal on the other copy of the DiskLabel.
            part = self.disk.format.partedDisk.getPartitionByPath(self.path)
            self.disk.format.removePartition(part)
            self.disk.format.commit()

    def deactivate(self):
        """
        This is never called. For instructional purposes only.

        We do not want multipath partitions disappearing upon their teardown().
        """
        if self.parents[0].type == 'dm-multipath':
            devmap = block.getMap(major=self.major, minor=self.minor)
            if devmap:
                try:
                    block.removeDeviceMap(devmap)
                except Exception as e:
                    raise DeviceTeardownError("failed to tear down device-mapper partition %s: %s" % (self.name, e))
            udev_settle()

    def _getSize(self):
        """ Get the device's size. """
        size = self._size
        if self.partedPartition:
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
            raise DeviceError("device does not exist", self.name)

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
        log_method_call(self, self.name, old=getattr(self.disk, "name", None),
                        new=getattr(disk, "name", None))
        if self.disk:
            self.disk.removeChild()

        if disk:
            self.parents = [disk]
            disk.addChild()
        else:
            self.parents = []

    disk = property(lambda p: p._getDisk(), lambda p,d: p._setDisk(d))

    @property
    def maxSize(self):
        """ The maximum size this partition can be. """
        # XXX Only allow growth up to the amount of free space following this
        #     partition on disk. We don't care about leading free space --
        #     a filesystem cannot be relocated, so if you want to use space
        #     before and after your partition, remove it and create a new one.
        sector = self.partedPartition.geometry.end + 1
        maxPartSize = self.size
        try:
            partition = self.partedPartition.disk.getPartitionBySector(sector)
        except _ped.PartitionException:
            pass
        else:
            if partition.type == parted.PARTITION_FREESPACE:
                maxPartSize = self.size + math.floor(partition.getSize())

        return min(self.format.maxSize, maxPartSize)

    @property
    def currentSize(self):
        """ The device's actual size. """
        if self.exists:
            return self._currentSize
        else:
            return 0

    @property
    def resizable(self):
        """ Can this type of device be resized? """
        return super(PartitionDevice, self).resizable and \
               self.disk.type != 'dasd'

    def checkSize(self):
        """ Check to make sure the size of the device is allowed by the
            format used.

            Returns:
            0  - ok
            1  - Too large
            -1 - Too small
        """
        if self.format.maxSize and self.size > self.format.maxSize:
            return 1
        elif (self.format.minSize and
              (not self.req_grow and
               self.size < self.format.minSize) or
              (self.req_grow and self.req_max_size and
               self.req_max_size < self.format.minSize)):
            return -1
        return 0

class DMDevice(StorageDevice):
    """ A device-mapper device """
    _type = "dm"
    _devDir = "/dev/mapper"

    def __init__(self, name, format=None, size=None, dmUuid=None,
                 target=None, exists=False, parents=None, sysfsPath=''):
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

    def __repr__(self):
        s = StorageDevice.__repr__(self)
        s += ("  target = %(target)s  dmUuid = %(dmUuid)s" %
              {"target": self.target, "dmUuid": self.dmUuid})
        return s

    @property
    def dict(self):
        d = super(DMDevice, self).dict
        d.update({"target": self.target, "dmUuid": self.dmUuid})
        return d

    @property
    def fstabSpec(self):
        """ Return the device specifier for use in /etc/fstab. """
        return self.path

    @property
    def mapName(self):
        """ This device's device-mapper map name """
        return self.name

    @property
    def status(self):
        _status = False
        for map in block.dm.maps():
            if map.name == self.mapName:
                _status = map.live_table and not map.suspended
                break

        return _status

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

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
            raise DeviceError("device has not been created", self.name)

        return dm.dm_node_from_name(self.name)

    def setupPartitions(self):
        log_method_call(self, name=self.name, kids=self.kids)
        rc = iutil.execWithRedirect("kpartx",
                                ["-a", "-s", self.path],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5")
        if rc:
            raise DMError("partition activation failed for '%s'" % self.name)
        udev_settle()

    def teardownPartitions(self):
        log_method_call(self, name=self.name, kids=self.kids)
        rc = iutil.execWithRedirect("kpartx",
                                ["-d", "-s", self.path],
                                stdout = "/dev/tty5",
                                stderr = "/dev/tty5")
        if rc:
            raise DMError("partition deactivation failed for '%s'" % self.name)
        udev_settle()

    def _setName(self, name):
        """ Set the device's map name. """
        log_method_call(self, self.name, status=self.status)
        if self.status:
            raise DeviceError("cannot rename active device", self.name)

        self._name = name
        #self.sysfsPath = "/dev/disk/by-id/dm-name-%s" % self.name

    name = property(lambda d: d._name,
                    lambda d,n: d._setName(n))

    @property
    def slave(self):
        """ This device's backing device. """
        return self.parents[0]


class DMLinearDevice(DMDevice):
    _type = "dm-linear"
    _partitionable = True
    _isDisk = True

    def __init__(self, name, format=None, size=None, dmUuid=None,
                 exists=False, parents=None, sysfsPath=''):
        """ Create a DMLinearDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                size -- the device's size (units/format TBD)
                dmUuid -- the device's device-mapper UUID
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                parents -- a list of required Device instances
                exists -- indicates whether this is an existing device
        """
        if not parents:
            raise ValueError("DMLinearDevice requires a backing block device")

        DMDevice.__init__(self, name, format=format, size=size,
                          parents=parents, sysfsPath=sysfsPath,
                          exists=exists, target="linear", dmUuid=dmUuid)

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        slave_length = self.slave.partedDevice.length
        dm.dm_create_linear(self.name, self.slave.path, slave_length,
                            self.dmUuid)

    def _postSetup(self):
        StorageDevice._postSetup(self)
        self.setupPartitions()
        udev_settle()

    def _teardown(self, recursive=False):
        self.teardownPartitions()
        udev_settle()
        dm.dm_remove(self.name)
        udev_settle()

    def deactivate(self, recursive=False):
        StorageDevice.teardown(self, recursive=recursive)

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        if not self._preTeardown(recursive=recursive):
            return

        log.debug("not tearing down dm-linear device %s" % self.name)

    @property
    def description(self):
        return self.model


class DMCryptDevice(DMDevice):
    """ A dm-crypt device """
    _type = "dm-crypt"

    def __init__(self, name, format=None, size=None, uuid=None,
                 exists=False, sysfsPath='', parents=None):
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
    _packages = ["cryptsetup-luks"]

    def __init__(self, name, format=None, size=None, uuid=None,
                 exists=False, sysfsPath='', parents=None):
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
        if not self.exists or not self.partedDevice:
            size = float(self.slave.size) - crypto.LUKS_METADATA_SIZE
        else:
            size = self.partedDevice.getSize()
        return size

    def _postCreate(self):
        self._name = self.slave.format.mapName
        StorageDevice._postCreate(self)

    def _postTeardown(self, recursive=False):
        if not recursive:
            # this is handled by StorageDevice._postTeardown if recursive
            # is True
            self.teardownParents(recursive=recursive)

        StorageDevice._postTeardown(self, recursive=recursive)

    def dracutSetupArgs(self):
        return set(["rd.luks.uuid=luks-%s" % self.slave.format.uuid])

class LVMVolumeGroupDevice(DMDevice):
    """ An LVM Volume Group

        XXX Maybe this should inherit from StorageDevice instead of
            DMDevice since there's no actual device.
    """
    _type = "lvmvg"
    _packages = ["lvm2"]

    def __init__(self, name, parents=None, size=None, free=None,
                 peSize=None, peCount=None, peFree=None, pvCount=None,
                 uuid=None, exists=False, sysfsPath=''):
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
                    uuid -- the VG's UUID

        """
        self.pvClass = get_device_format_class("lvmpv")
        if not self.pvClass:
            raise StorageError("cannot find 'lvmpv' class")

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
        self.lv_names = []
        self.lv_uuids = []
        self.lv_sizes = []
        self.lv_attr = []
        self.hasDuplicate = False
        self.reserved_percent = 0
        self.reserved_space = 0

        # circular references, here I come
        self._lvs = []

        # TODO: validate peSize if given
        if not self.peSize:
            self.peSize = lvm.LVM_PE_SIZE  # MB

        if not self.exists:
            self.pvCount = len(self.parents)

        # Some snapshots don't have a proper LV as an origin (--vorigin).
        # They still occupy space in the VG.
        self.voriginSnapshots = {}

    def __repr__(self):
        s = DMDevice.__repr__(self)
        s += ("  free = %(free)s  PE Size = %(peSize)s  PE Count = %(peCount)s\n"
              "  PE Free = %(peFree)s  PV Count = %(pvCount)s\n"
              "  LV Names = %(lv_names)s  modified = %(modified)s\n"
              "  extents = %(extents)s  free space = %(freeSpace)s\n"
              "  free extents = %(freeExtents)s"
              "  reserved percent = %(rpct)s  reserved space = %(res)s\n"
              "  PVs = %(pvs)s\n"
              "  LVs = %(lvs)s" %
              {"free": self.free, "peSize": self.peSize, "peCount": self.peCount,
               "peFree": self.peFree, "pvCount": self.pvCount,
               "lv_names": self.lv_names, "modified": self.isModified,
               "extents": self.extents, "freeSpace": self.freeSpace,
               "freeExtents": self.freeExtents,
               "rpct": self.reserved_percent, "res": self.reserved_space,
               "pvs": pprint.pformat([str(p) for p in self.pvs]),
               "lvs": pprint.pformat([str(l) for l in self.lvs])})
        return s

    @property
    def dict(self):
        d = super(LVMVolumeGroupDevice, self).dict
        d.update({"free": self.free, "peSize": self.peSize,
                  "peCount": self.peCount, "peFree": self.peFree,
                  "pvCount": self.pvCount, "extents": self.extents,
                  "freeSpace": self.freeSpace,
                  "freeExtents": self.freeExtents,
                  "lv_names": self.lv_names,
                  "lv_uuids": self.lv_uuids,
                  "lv_sizes": self.lv_sizes,
                  "lv_attr": self.lv_attr,
                  "reserved_percent": self.reserved_percent,
                  "reserved_space": self.reserved_space,
                  "lvNames": [lv.name for lv in self.lvs]})
        return d

    @property
    def mapName(self):
        """ This device's device-mapper map name """
        # Thank you lvm for this lovely hack.
        return self.name.replace("-","--")

    @property
    def path(self):
        """ Device node representing this device. """
        return "%s/%s" % (self._devDir, self.mapName)

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        self.sysfsPath = ''

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
        if not self.complete:
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
            raise DeviceError("device does not exist", self.name)

        if not isinstance(device.format, self.pvClass):
            raise ValueError("addDevice requires a PV arg")

        if self.uuid and device.format.vgUuid != self.uuid:
            # this means there is another vg with the same name on the system
            # set hasDuplicate which will make complete return False
            # and let devicetree._handleInconsistencies() further handle this.
            # Note we still add the device to our parents for use by
            # devicetree._handleInconsistencies()
            self.hasDuplicate = True

        if device in self.pvs:
            raise ValueError("device is already a member of this VG")

        self.parents.append(device)
        device.addChild()

        # now see if the VG can be activated
        if self.complete:
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
        except ValueError:
            raise ValueError("cannot remove non-member PV device from VG")

        device.removeChild()

    def _preSetup(self, orig=False):
        if self.exists and not self.complete:
            raise DeviceError("cannot activate VG with missing PV(s)", self.name)
        return StorageDevice._preSetup(self, orig=orig)

    def _teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        lvm.vgdeactivate(self.name)

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        pv_list = [pv.path for pv in self.parents]
        lvm.vgcreate(self.name, pv_list, self.peSize)

    def _preDestroy(self):
        StorageDevice._preDestroy(self)
        # set up the pvs since lvm needs access to them to do the vgremove
        self.setupParents(orig=True)

    def _destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        if not self.complete:
            for pv in self.pvs:
                # Remove the PVs from the ignore filter so we can wipe them.
                lvm.lvm_cc_removeFilterRejectRegexp(pv.name)

            # Don't run vgremove or vgreduce since there may be another VG with
            # the same name that we want to keep/use.
            return

        lvm.vgreduce(self.name, [], rm=True)
        lvm.vgdeactivate(self.name)
        lvm.vgremove(self.name)

    def reduce(self, pv_list):
        """ Remove the listed PVs from the VG. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        lvm.vgreduce(self.name, pv_list)
        # XXX do we need to notify the kernel?

    def _addLogVol(self, lv):
        """ Add an LV to this VG. """
        if lv in self._lvs:
            raise ValueError("lv is already part of this vg")

        # verify we have the space, then add it
        # do not verify for growing vg (because of ks)
        if not lv.exists and not self.growable and lv.size > self.freeSpace:
            raise DeviceError("new lv is too large to fit in free space", self.name)

        log.debug("Adding %s/%dMB to %s" % (lv.name, lv.size, self.name))
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
            raise DeviceError("cannot add pv to existing vg", self.name)

        self.parents.append(pv)
        pv.addChild()

        # and update our pv count
        self.pvCount = len(self.parents)

    def addMember(self, member):
        self._addPV(member)

    def _removePV(self, pv):
        """ Remove an PV from this VG. """
        if not pv in self.pvs:
            raise ValueError("specified pv is not part of this vg")

        # for the time being we will not allow vgreduce
        if self.exists:
            raise DeviceError("cannot remove pv from existing vg", self.name)

        self.parents.remove(pv)
        pv.removeChild()

        # and update our pv count
        self.pvCount = len(self.parents)

    def removeMember(self, member):
        self._removePV(member)

    # We can't rely on lvm to tell us about our size, free space, &c
    # since we could have modifications queued, unless the VG and all of
    # its PVs already exist.
    #
    #        -- liblvm may contain support for in-memory devices

    @property
    def isModified(self):
        """ Return True if the VG has changes queued that LVM is unaware of. """
        modified = True
        if self.exists and not filter(lambda d: not d.exists, self.pvs):
            modified = False

        return modified

    @property
    def snapshotSpace(self):
        """ Total space used by snapshots in this volume group. """
        used = 0
        for lv in self.lvs:
            used += self.align(lv.snapshotSpace, roundup=True)

        for (vname, vsize) in self.voriginSnapshots.items():
            used += self.align(vsize, roundup=True)

        return used

    @property
    def reservedSpace(self):
        """ Reserved space in this VG, in MB """
        reserved = 0
        if self.reserved_percent > 0:
            reserved = self.reserved_percent * 0.01 * self.size
        elif self.reserved_space > 0:
            reserved = self.reserved_space

        return self.align(reserved, roundup=True)

    @property
    def size(self):
        """ The size of this VG """
        # TODO: just ask lvm if isModified returns False

        # sum up the sizes of the PVs and align to pesize
        size = 0
        for pv in self.pvs:
            size += max(0, self.align(pv.size - pv.format.peStart))

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
        log.debug("%s size is %dMB" % (self.name, self.size))
        used = sum(lv.vgSpaceUsed for lv in self.lvs) + self.snapshotSpace
        used += self.reservedSpace
        free = self.size - used
        log.debug("vg %s has %dMB free" % (self.name, free))
        return free

    @property
    def freeExtents(self):
        """ The number of free extents in this VG. """
        # TODO: just ask lvm if isModified returns False
        return self.freeSpace / self.peSize

    def align(self, size, roundup=None):
        """ Align a size to a multiple of physical extent size. """
        size = numeric_type(size)

        if roundup:
            round = math.ceil
        else:
            round = math.floor

        # we want Kbytes as a float for our math
        size *= 1024.0
        pesize = self.peSize * 1024.0
        return long((round(size / pesize) * pesize) / 1024)

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
        # vgs with duplicate names are overcomplete, which is not what we want
        if self.hasDuplicate:
            return False

        return len(self.pvs) == self.pvCount or not self.exists


class LVMLogicalVolumeDevice(DMDevice):
    """ An LVM Logical Volume """
    _type = "lvmlv"
    _resizable = True
    _packages = ["lvm2"]

    def __init__(self, name, parents=None, size=None, uuid=None,
                 stripes=1, logSize=0, snapshotSpace=0,
                 format=None, exists=False, sysfsPath='',
                 grow=None, maxsize=None, percent=None,
                 singlePV=False):
        """ Create a LVMLogicalVolumeDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)
                vgdev -- volume group (LVMVolumeGroupDevice instance)

            Keyword Arguments:

                size -- the device's size (in MB)
                uuid -- the device's UUID
                stripes -- number of copies in the vg (>1 for mirrored lvs)
                logSize -- size of log volume (for mirrored lvs)
                snapshotSpace -- sum of sizes of snapshots of this lv
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                exists -- indicates whether this is an existing device
                singlePV -- if true, maps this lv to a single pv

                For new (non-existent) LVs only:

                    grow -- whether to grow this LV
                    maxsize -- maximum size for growable LV (in MB)
                    percent -- percent of VG space to take

        """
        if isinstance(parents, list):
            if len(parents) != 1:
                raise ValueError("constructor requires a single LVMVolumeGroupDevice instance")
            elif not isinstance(parents[0], LVMVolumeGroupDevice):
                raise ValueError("constructor requires a LVMVolumeGroupDevice instance")
        elif not isinstance(parents, LVMVolumeGroupDevice):
            raise ValueError("constructor requires a LVMVolumeGroupDevice instance")
        DMDevice.__init__(self, name, size=size, format=format,
                          sysfsPath=sysfsPath, parents=parents,
                          exists=exists)

        self.singlePVerr = ("%(mountpoint)s is restricted to a single "
                            "physical volume on this platform.  No physical "
                            "volumes available in volume group %(vgname)s "
                            "with %(size)d MB of available space." %
                           {'mountpoint': getattr(self.format, "mountpoint",
                                                  "A proposed logical volume"),
                            'vgname': self.vg.name,
                            'size': self.size})

        self.uuid = uuid
        self.snapshotSpace = snapshotSpace
        self.stripes = stripes
        self.logSize = logSize
        self.singlePV = singlePV

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

        if self.singlePV:
            # make sure there is at least one PV that can hold this LV
            validpvs = filter(lambda x: float(x.size) >= self.req_size,
                              self.vg.pvs)
            if not validpvs:
                for dev in self.parents:
                    dev.removeChild()
                raise SinglePhysicalVolumeError(self.singlePVerr)

        # here we go with the circular references
        self.vg._addLogVol(self)

    def __repr__(self):
        s = DMDevice.__repr__(self)
        s += ("  VG device = %(vgdev)r\n"
              "  percent = %(percent)s\n"
              "  mirrored = %(mirrored)s stripes = %(stripes)d"
              "  snapshot total =  %(snapshots)dMB\n"
              "  VG space used = %(vgspace)dMB" %
              {"vgdev": self.vg, "percent": self.req_percent,
               "mirrored": self.mirrored, "stripes": self.stripes,
               "snapshots": self.snapshotSpace, "vgspace": self.vgSpaceUsed })
        return s

    @property
    def dict(self):
        d = super(LVMLogicalVolumeDevice, self).dict
        if self.exists:
            d.update({"mirrored": self.mirrored, "stripes": self.stripes,
                      "snapshots": self.snapshotSpace,
                      "vgspace": self.vgSpaceUsed})
        else:
            d.update({"percent": self.req_percent})

        return d

    @property
    def mirrored(self):
        return self.stripes > 1

    def _setSize(self, size):
        size = self.vg.align(numeric_type(size))
        log.debug("trying to set lv %s size to %dMB" % (self.name, size))
        if size <= self.vg.freeSpace + self.vgSpaceUsed:
            self._size = size
            self.targetSize = size
        else:
            log.debug("failed to set size: %dMB short" % (size - (self.vg.freeSpace + self.vgSpaceUsed),))
            raise ValueError("not enough free space in volume group")

    size = property(StorageDevice._getSize, _setSize)

    @property
    def vgSpaceUsed(self):
        """ Space occupied by this LV, not including snapshots. """
        return (self.vg.align(self.size, roundup=True) * self.stripes
                + self.logSize)

    @property
    def vg(self):
        """ This Logical Volume's Volume Group. """
        return self.parents[0]

    @property
    def mapName(self):
        """ This device's device-mapper map name """
        # Thank you lvm for this lovely hack.
        return "%s-%s" % (self.vg.mapName, self._name.replace("-","--"))

    @property
    def path(self):
        """ Device node representing this device. """
        return "%s/%s" % (self._devDir, self.mapName)

    def getDMNode(self):
        """ Return the dm-X (eg: dm-0) device node for this device. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        return dm.dm_node_from_name(self.mapName)

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

    def setupParents(self, orig=False):
        # parent is a vg, which has no formatting (or device for that matter)
        Device.setupParents(self, orig=orig)

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        lvm.lvactivate(self.vg.name, self._name)

    def _teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        lvm.lvdeactivate(self.vg.name, self._name)

    def _postTeardown(self, recursive=False):
        try:
            # It's likely that teardown of a VG will fail due to other
            # LVs being active (filesystems mounted, &c), so don't let
            # it bring everything down.
            StorageDevice._postTeardown(self, recursive=recursive)
        except StorageError:
            if recursive:
                log.debug("vg %s teardown failed; continuing" % self.vg.name)
            else:
                raise

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        # should we use --zero for safety's sake?
        if self.singlePV:
            lvm.lvcreate(self.vg.name, self._name, self.size,
                         pvs=self._getSinglePV())
        else:
            lvm.lvcreate(self.vg.name, self._name, self.size)

    def _preDestroy(self):
        StorageDevice._preDestroy(self)
        # set up the vg's pvs so lvm can remove the lv
        self.vg.setupParents(orig=True)

    def _destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        lvm.lvremove(self.vg.name, self._name)

    def _getSinglePV(self):
        validpvs = filter(lambda x: float(x.size) >= self.size, self.vg.pvs)

        if not validpvs:
            raise SinglePhysicalVolumeError(self.singlePVerr)

        return [validpvs[0].path]

    def resize(self):
        log_method_call(self, self.name, status=self.status)
        self._preDestroy()

        # Setup VG parents (in case they are dmraid partitions for example)
        self.vg.setupParents(orig=True)

        if self.originalFormat.exists:
            self.originalFormat.teardown()
        if self.format.exists:
            self.format.teardown()

        udev_settle()
        lvm.lvresize(self.vg.name, self._name, self.size)

    def dracutSetupArgs(self):
        # Note no mapName usage here, this is a lvm cmdline name, which
        # is different (ofcourse)
        return set(["rd.lvm.lv=%s/%s" % (self.vg.name, self._name)])

    def checkSize(self):
        """ Check to make sure the size of the device is allowed by the
            format used.

            Returns:
            0  - ok
            1  - Too large
            -1 - Too small
        """
        if self.format.maxSize and self.size > self.format.maxSize:
            return 1
        elif (self.format.minSize and
              (not self.req_grow and
               self.size < self.format.minSize) or
              (self.req_grow and self.req_max_size and
               self.req_max_size < self.format.minSize)):
            return -1
        return 0

class MDRaidArrayDevice(StorageDevice):
    """ An mdraid (Linux RAID) device. """
    _type = "mdarray"
    _packages = ["mdadm"]
    _devDir = "/dev/md"

    def __init__(self, name, level=None, major=None, minor=None, size=None,
                 memberDevices=None, totalDevices=None,
                 uuid=None, format=None, exists=False, metadataVersion=None,
                 parents=None, sysfsPath=''):
        """ Create a MDRaidArrayDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)

            Keyword Arguments:

                level -- the device's RAID level (a string, eg: '1' or 'raid1')
                metadataVersion -- the version of the device's md metadata
                parents -- list of member devices (StorageDevice instances)
                size -- the device's size (units/format TBD)
                uuid -- the device's UUID
                minor -- the device minor
                sysfsPath -- sysfs device path
                format -- a DeviceFormat instance
                exists -- indicates whether this is an existing device
        """
        StorageDevice.__init__(self, name, format=format, exists=exists,
                               major=major, minor=minor, size=size,
                               parents=parents, sysfsPath=sysfsPath)

        self.level = level
        if level == "container":
            self._type = "mdcontainer"
        elif level is not None:
            self.level = mdraid.raidLevel(level)

        # For new arrays check if we have enough members
        if (not exists and parents and
                len(parents) < mdraid.get_raid_min_members(self.level)):
            for dev in self.parents:
                dev.removeChild()
            raise DeviceError, P_("A RAID%(raidLevel)d set requires at least %(minMembers)d member",
                                 "A RAID%(raidLevel)d set requires at least %(minMembers)d members",
                                 mdraid.get_raid_min_members(self.level)) % \
                                 {"raidLevel": self.level, "minMembers": mdraid.get_raid_min_members(self.level)}

        self.uuid = uuid
        self._totalDevices = numeric_type(totalDevices)
        self._memberDevices = numeric_type(memberDevices)

        self.chunkSize = 512.0 / 1024.0         # chunk size in MB

        if not self.exists and not isinstance(metadataVersion, str):
            self.metadataVersion = "default"
        else:
            self.metadataVersion = metadataVersion

        # bitmaps are not meaningful on raid0 according to mdadm-3.0.3
        self.createBitmap = self.level != 0

        # For container members probe size now, as we cannot determine it
        # when teared down.
        if self.parents and self.parents[0].type == "mdcontainer":
            self._size = self.currentSize
            self._type = "mdbiosraidarray"

        self.formatClass = get_device_format_class("mdmember")
        if not self.formatClass:
            for dev in self.parents:
                dev.removeChild()
            raise DeviceError("cannot find class for 'mdmember'", self.name)

        if self.exists and self.uuid and not flags.testing:
            # this is a hack to work around mdadm's insistence on giving
            # really high minors to arrays it has no config entry for
            open("/etc/mdadm.conf", "a").write("ARRAY %s UUID=%s\n"
                                                % (self.path, self.uuid))

    @property
    def rawArraySize(self):
        """ Calculate the raw array size without taking into account space
        reserved for metadata or chunkSize alignment.

        This is used to calculate the superBlockSize for v1.1 and v1.2
        metadata.

        Returns the raw size in MB
        """
        smallestMemberSize = self.smallestMember.size
        if self.level == mdraid.RAID0:
            size = self.memberDevices * smallestMemberSize
        elif self.level == mdraid.RAID1:
            size = smallestMemberSize
        elif self.level == mdraid.RAID4:
            size = (self.memberDevices - 1) * smallestMemberSize
        elif self.level == mdraid.RAID5:
            size = (self.memberDevices - 1) * smallestMemberSize
        elif self.level == mdraid.RAID6:
            size = (self.memberDevices - 2) * smallestMemberSize
        elif self.level == mdraid.RAID10:
            size = (self.memberDevices / 2.0) * smallestMemberSize
        else:
            size = smallestMemberSize
            log.error("unknown RAID level %s" % (self.level))
        log.debug("raw RAID %s size == %s" % (self.level, size))
        return size

    @property
    def superBlockSize(self):
        """ mdadm has different amounts of space reserved for its use depending
        on the metadata type and size of the array.

        0.9 use 2.0 MB
        1.0 use 2.0 MB
        1.1 or 1.2 use the formula lifted from mdadm/super1.c to calculate it
        based on the array size.
        """
        # mdadm 3.2.4 made a major change in the amount of space used for 1.1 and 1.2
        # in order to reserve space for reshaping. See commit 508a7f16 in the
        # upstream mdadm repository.
        if self.metadataVersion not in ["default", "1.1", "1.2"]:
            headroom = 2.0
        else:
            array_size = self.rawArraySize
            # MDADM: We try to leave 0.1% at the start for reshape
            # MDADM: operations, but limit this to 128Meg (0.1% of 10Gig)
            # MDADM: which is plenty for efficient reshapes
            # NOTE: In the mdadm code this is in 512b sectors. Converted to use MB
            headroom = 128
            while headroom << 10 > array_size:
                headroom >>= 1
        log.info("Using %sMB superBlockSize" % (headroom))
        return headroom

    @property
    def smallestMember(self):
        try:
            smallest = sorted(self.devices, key=lambda d: d.size)[0]
        except IndexError:
            smallest = None
        return smallest

    @property
    def size(self):
        if not self.devices:
            return 0

        # For container members return probed size, as we cannot determine it
        # when teared down.
        if self.type == "mdbiosraidarray":
            return self._size

        size = 0
        smallestMemberSize = self.smallestMember.size - self.superBlockSize
        if not self.exists or not self.partedDevice:
            if self.level == mdraid.RAID0:
                size = self.memberDevices * smallestMemberSize
                size -= size % self.chunkSize
            elif self.level == mdraid.RAID1:
                size = smallestMemberSize
            elif self.level == mdraid.RAID4:
                size = (self.memberDevices - 1) * smallestMemberSize
                size -= size % self.chunkSize
            elif self.level == mdraid.RAID5:
                size = (self.memberDevices - 1) * smallestMemberSize
                size -= size % self.chunkSize
            elif self.level == mdraid.RAID6:
                size = (self.memberDevices - 2) * smallestMemberSize
                size -= size % self.chunkSize
            elif self.level == mdraid.RAID10:
                size = (self.memberDevices / 2.0) * smallestMemberSize
                size -= size % self.chunkSize
            log.debug("non-existent RAID %s size == %s" % (self.level, size))
        else:
            size = self.partedDevice.getSize()
            log.debug("existing RAID %s size == %s" % (self.level, size))

        return size

    @property
    def description(self):
        if self.level == mdraid.RAID0:
            levelstr = "stripe"
        elif self.level == mdraid.RAID1:
            levelstr = "mirror"
        else:
            levelstr = "raid%s" % self.level

        if self.type == "mdcontainer":
            return "BIOS RAID container"
        elif self.type == "mdbiosraidarray":
            return "BIOS RAID set (%s)" % levelstr
        else:
            return "MDRAID set (%s)" % levelstr

    def __repr__(self):
        s = StorageDevice.__repr__(self)
        s += ("  level = %(level)s  spares = %(spares)s\n"
              "  members = %(memberDevices)s\n"
              "  total devices = %(totalDevices)s"
              "  metadata version = %(metadataVersion)s" %
              {"level": self.level, "spares": self.spares,
               "memberDevices": self.memberDevices,
               "totalDevices": self.totalDevices,
               "metadataVersion": self.metadataVersion})
        return s

    @property
    def dict(self):
        d = super(MDRaidArrayDevice, self).dict
        d.update({"level": self.level,
                  "spares": self.spares, "memberDevices": self.memberDevices,
                  "totalDevices": self.totalDevices,
                  "metadataVersion": self.metadataVersion})
        return d

    @property
    def mdadmConfEntry(self):
        """ This array's mdadm.conf entry. """
        if self.level is None or self.memberDevices is None or not self.uuid:
            raise DeviceError("array is not fully defined", self.name)

        # containers and the sets within must only have a UUID= parameter
        if self.type == "mdcontainer" or self.type == "mdbiosraidarray":
            fmt = "ARRAY %s UUID=%s\n"
            return fmt % (self.path, self.uuid)

        fmt = "ARRAY %s level=raid%d num-devices=%d UUID=%s\n"
        return fmt % (self.path, self.level, self.memberDevices, self.uuid)

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
            if self.totalDevices is not None and \
               self.totalDevices > self.memberDevices:
                spares = self.totalDevices - self.memberDevices
            elif self.totalDevices is None:
                spares = self.memberDevices
                self._totalDevices = self.memberDevices
        return spares

    def _setSpares(self, spares):
        # FIXME: this is too simple to be right
        if self.totalDevices > spares:
            self.memberDevices = self.totalDevices - spares

    spares = property(_getSpares, _setSpares)

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        # We don't use self.status here because self.status requires a valid
        # sysfs path to function correctly.
        if os.path.exists(self.path):
            md_node = mdraid.md_node_from_name(self.name)
            self.sysfsPath = "/devices/virtual/block/%s" % md_node
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
            raise DeviceError("device has not been created", self.name)

        if not isinstance(device.format, self.formatClass):
            raise ValueError("invalid device format for mdraid member")

        if self.uuid and device.format.mdUuid != self.uuid:
            raise ValueError("cannot add member with non-matching UUID")

        if device in self.devices:
            raise ValueError("device is already a member of this array")

        # we added it, so now set up the relations
        self.devices.append(device)
        device.addChild()

        device.setup()
        udev_settle()

        if self.spares > 0:
            # mdadm doesn't like it when you try to incrementally add spares
            return

        try:
            mdraid.mdadd(device.path)
            # mdadd causes udev events
            udev_settle()
        except MDRaidError as e:
            log.warning("failed to add member %s to md array %s: %s"
                        % (device.path, self.path, e))

        if self.status:
            # we always probe since the device may not be set up when we want
            # information about it
            self._size = self.currentSize

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

    def addMember(self, member):
        if member in self.parents:
            raise ValueError("member is already part of this array")

        # for the time being we will not allow adding members to existing arrays
        if self.exists:
            raise DeviceError("cannot add member to existing array", self.name)

        self.parents.append(member)
        member.addChild()
        self.memberDevices += 1

    def removeMember(self, member):
        self._removeDevice(member)
        self.memberDevices -= 1

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
            if state in ("clean", "active", "active-idle", "readonly", "read-auto"):
                status = True
            # mdcontainers have state inactive when started (clear if stopped)
            if self.type == "mdcontainer" and state == "inactive":
                status = True

        return status

    @property
    def degraded(self):
        """ Return True if the array is running in degraded mode. """
        rc = False
        degraded_file = "/sys/%s/md/degraded" % self.sysfsPath
        if os.access(degraded_file, os.R_OK):
            val = open(degraded_file).read().strip()
            if val == "1":
                rc = True

        return rc

    @property
    def complete(self):
        if self.type == "mdbiosraidarray":
            members = len(self.parents[0].parents)
        else:
            members = len(self.parents)

        return (self.memberDevices <= members) or not self.exists

    @property
    def devices(self):
        """ Return a list of this array's member device instances. """
        return self.parents

    def _postSetup(self):
        super(MDRaidArrayDevice, self)._postSetup()
        self.updateSysfsPath()

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        disks = []
        for member in self.devices:
            member.setup(orig=orig)
            disks.append(member.path)

        mdraid.mdactivate(self.path,
                          members=disks,
                          uuid=self.uuid)

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        # we don't really care about the return value of _preTeardown here.
        # see comment just above mddeactivate call
        self._preTeardown(recursive=recursive)

        # Since BIOS RAID sets (containers in mdraid terminology) never change
        # there is no need to stop them and later restart them. Not stopping
        # (and thus also not starting) them also works around bug 523334
        if self.type == "mdcontainer" or self.type == "mdbiosraidarray":
            return

        # We don't really care what the array's state is. If the device
        # file exists, we want to deactivate it. mdraid has too many
        # states.
        if self.exists and os.path.exists(self.path):
            mdraid.mddeactivate(self.path)

        self._postTeardown(recursive=recursive)

    def preCommitFixup(self, *args, **kwargs):
        """ Determine create parameters for this set """
        mountpoints = kwargs.pop("mountpoints")
        log_method_call(self, self.name, mountpoints)

        if "/boot" in mountpoints:
            bootmountpoint = "/boot"
        else:
            bootmountpoint = "/"

        # If we are used to boot from we cannot use 1.1 metadata
        if getattr(self.format, "mountpoint", None) == bootmountpoint or \
           getattr(self.format, "mountpoint", None) == "/boot/efi" or \
           self.format.type == "prepboot":
            self.metadataVersion = "1.0"

        # Bitmaps are not useful for swap and small partitions
        if self.size < 1000 or self.format.type == "swap":
            self.createBitmap = False

    def _postCreate(self):
        # this is critical since our status method requires a valid sysfs path
        md_node = mdraid.md_node_from_name(self.name)
        self.sysfsPath = "/devices/virtual/block/%s" % md_node
        self.exists = True  # I think we can remove this.

        StorageDevice._postCreate(self)

        # update our uuid attribute with the new array's UUID
        info = udev_get_block_device(self.sysfsPath)
        self.uuid = udev_device_get_md_uuid(info)
        for member in self.devices:
            member.mdUuid = self.uuid

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        disks = [disk.path for disk in self.devices]
        spares = len(self.devices) - self.memberDevices
        mdraid.mdcreate(self.path,
                        self.level,
                        disks,
                        spares,
                        metadataVer=self.metadataVersion,
                        bitmap=self.createBitmap)

    @property
    def formatArgs(self):
        formatArgs = []
        if self.format.type == "ext2":
            if self.level == mdraid.RAID5:
                formatArgs = ['-R',
                              'stride=%d' % ((self.memberDevices - 1) * 16)]
            if self.level == mdraid.RAID4:
                formatArgs = ['-R',
                              'stride=%d' % ((self.memberDevices - 1) * 16)]
            elif self.level == mdraid.RAID0:
                formatArgs = ['-R',
                              'stride=%d' % (self.memberDevices * 16)]

    @property
    def mediaPresent(self):
        # Containers should not get any format handling done
        # (the device node does not allow read / write calls)
        if self.type == "mdcontainer":
            return False
        # BIOS RAID sets should show as present even when teared down
        elif self.type == "mdbiosraidarray":
            return True
        elif flags.testing:
            return True
        else:
            return self.partedDevice is not None

    @property
    def model(self):
        return self.description

    @property
    def partitionable(self):
        return self.type == "mdbiosraidarray"

    @property
    def isDisk(self):
        return self.type == "mdbiosraidarray"

    def dracutSetupArgs(self):
        return set(["rd.md.uuid=%s" % self.uuid])

class DMRaidArrayDevice(DMDevice):
    """ A dmraid (device-mapper RAID) device """
    _type = "dm-raid array"
    _packages = ["dmraid"]
    _partitionable = True
    _isDisk = True

    def __init__(self, name, raidSet=None, format=None,
                 size=None, parents=None, sysfsPath=''):
        """ Create a DMRaidArrayDevice instance.

            Arguments:

                name -- the dmraid name also the device node's basename

            Keyword Arguments:

                raidSet -- the RaidSet object from block
                parents -- a list of the member devices
                sysfsPath -- sysfs device path
                size -- the device's size
                format -- a DeviceFormat instance
        """
        if isinstance(parents, list):
            for parent in parents:
                if not parent.format or parent.format.type != "dmraidmember":
                    raise ValueError("parent devices must contain dmraidmember format")
        DMDevice.__init__(self, name, format=format, size=size,
                          parents=parents, sysfsPath=sysfsPath, exists=True)

        self.formatClass = get_device_format_class("dmraidmember")
        if not self.formatClass:
            raise StorageError("cannot find class for 'dmraidmember'")

        self._raidSet = raidSet

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
            raise DeviceError("device has not been created", self.name)

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

    def deactivate(self):
        """ Deactivate the raid set. """
        log_method_call(self, self.name, status=self.status)
        # This call already checks if the set is not active.
        self._raidSet.deactivate()

    def activate(self):
        """ Activate the raid set. """
        log_method_call(self, self.name, status=self.status)
        # This call already checks if the set is active.
        self._raidSet.activate(mknod=True)
        udev_settle()

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        self.activate()

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        if not self._preTeardown(recursive=recursive):
            return

        log.debug("not tearing down dmraid device %s" % self.name)

    @property
    def description(self):
        return "BIOS RAID set (%s)" % self._raidSet.rs.set_type

    @property
    def model(self):
        return self.description

    def dracutSetupArgs(self):
        return set(["rd.dm.uuid=%s" % self.name])

class MultipathDevice(DMDevice):
    """ A multipath device """
    _type = "dm-multipath"
    _packages = ["device-mapper-multipath"]
    _services = ["multipathd"]
    _partitionable = True
    _isDisk = True

    def __init__(self, name, info, format=None, size=None,
                 parents=None, sysfsPath=''):
        """ Create a MultipathDevice instance.

            Arguments:

                name -- the device name (generally a device node's basename)
                info -- the udev info for this device

            Keyword Arguments:

                sysfsPath -- sysfs device path
                size -- the device's size
                format -- a DeviceFormat instance
                parents -- a list of the backing devices (Device instances)
        """

        self._info = info
        self.setupIdentity()
        DMDevice.__init__(self, name, format=format, size=size,
                          parents=parents, sysfsPath=sysfsPath,
                          exists=True)

        self.config = {
            'wwid' : self.identity,
            'mode' : '0600',
            'uid' : '0',
            'gid' : '0',
        }

    def setupIdentity(self):
        """ Adds identifying remarks to MultipathDevice object.
        
            May be overridden by a sub-class for e.g. RDAC handling.
        """
        self._identity = self._info.get("ID_SERIAL_RAW", self._info.get("ID_SERIAL_SHORT"))

    @property
    def identity(self):
        """ Get identity set with setupIdentityFromInfo()
        
            May be overridden by a sub-class for e.g. RDAC handling.
        """
        if not hasattr(self, "_identity"):
            raise RuntimeError, "setupIdentityFromInfo() has not been called."
        return self._identity

    @property
    def wwid(self):
        identity = self.identity
        ret = []
        while identity:
            ret.append(identity[:2])
            identity = identity[2:]
        return ":".join(ret)

    @property
    def model(self):
        if not self.parents:
            return ""
        return self.parents[0].model

    @property
    def vendor(self):
        if not self.parents:
            return ""
        return self.parents[0].vendor

    @property
    def description(self):
        return "WWID %s" % (self.wwid,)

    def addParent(self, parent):
        """ Add a parent device to the mpath. """
        log_method_call(self, self.name, status=self.status)
        if self.status:
            self.teardown()
            self.parents.append(parent)
            self.setup()
        else:
            self.parents.append(parent)

    def deactivate(self):
        """ 
        This is never called, included just for documentation.

        If we called this during teardown(), we wouldn't be able to get parted
        object because /dev/mapper/mpathX wouldn't exist.
        """
        if self.exists and os.path.exists(self.path):
            #self.teardownPartitions()
            #rc = iutil.execWithRedirect("multipath",
            #                    ['-f', self.name],
            #                    stdout = "/dev/tty5",
            #                    stderr = "/dev/tty5")
            #if rc:
            #    raise MPathError("multipath deactivation failed for '%s'" %
            #                    self.name)
            bdev = block.getDevice(self.name)
            devmap = block.getMap(major=bdev[0], minor=bdev[1])
            if devmap.open_count:
                return
            try:
                block.removeDeviceMap(devmap)
            except Exception as e:
                raise MPathError("failed to tear down multipath device %s: %s"
                                % (self.name, e))

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        udev_settle()
        rc = iutil.execWithRedirect("multipath",
                            [self.name],
                            stdout = "/dev/tty5",
                            stderr = "/dev/tty5")
        if rc:
            raise MPathError("multipath activation failed for '%s'" %
                            self.name, hardware_fault=True)

    def _postSetup(self):
        StorageDevice._postSetup(self)
        self.setupPartitions()
        udev_settle()

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
            name = "none"

        StorageDevice.__init__(self, name, format=format, exists=True)

    @property
    def path(self):
        """ Device node representing this device. """
        return self.name

    def setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)

    def teardown(self, recursive=False):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        # just make sure the format is unmounted
        self._preTeardown(recursive=recursive)

    def create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        self._preDestroy()


class FileDevice(StorageDevice):
    """ A file on a filesystem.

        This exists because of swap files.
    """
    _type = "file"
    _devDir = ""

    def __init__(self, path, format=None, size=None,
                 exists=False, parents=None):
        """ Create a FileDevice instance.

            Arguments:

                path -- full path to the file

            Keyword Arguments:

                format -- a DeviceFormat instance
                size -- the file size (units TBD)
                parents -- a list of required devices (Device instances)
                exists -- indicates whether this is an existing device
        """
        if not path.startswith("/"):
            raise ValueError("FileDevice requires an absolute path")

        StorageDevice.__init__(self, path, format=format, size=size,
                               exists=exists, parents=parents)

    @property
    def fstabSpec(self):
        return self.name

    @property
    def path(self):
        root = ""
        try:
            status = self.parents[0].format.status
        except (AttributeError, IndexError):
            # either this device has no parents or something is wrong with
            # the first one
            status = (os.access(self.name, os.R_OK) and
                      self.parents in ([], None))
        else:
            # this is the actual active mountpoint
            root = self.parents[0].format._mountpoint
            # trim the mountpoint down to the chroot since we already have
            # the otherwise fully-qualified path
            mountpoint = self.parents[0].format.mountpoint
            while mountpoint.endswith("/"):
                mountpoint = mountpoint[:-1]
            if mountpoint:
                root = root[:-len(mountpoint)]

        return os.path.normpath("%s%s" % (root, self.name))

    def _preSetup(self, orig=False):
        if self.format and self.format.exists and not self.format.status:
            self.format.device = self.path

        return StorageDevice._preSetup(self, orig=orig)

    def _preTeardown(self, recursive=None):
        if self.format and self.format.exists and not self.format.status:
            self.format.device = self.path

        return StorageDevice._preTeardown(self, recursive=recursive)

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        fd = os.open(self.path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC)
        buf = "\0" * 1024 * 1024
        for n in range(self.size):
            os.write(fd, buf)
        os.close(fd)

    def _destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)
        os.unlink(self.path)


class SparseFileDevice(FileDevice):
    """A sparse file on a filesystem.
    This exists for sparse disk images."""
    _type = "sparse file"
    def _create(self):
        """Create a sparse file."""
        log_method_call(self, self.name, status=self.status)
        fd = os.open(self.path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC)
        os.ftruncate(fd, 1024*1024*self.size)
        os.close(fd)


class DirectoryDevice(FileDevice):
    """ A directory on a filesystem.

        This exists because of bind mounts.
    """
    _type = "directory"

    def _create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        iutil.mkdirChain(self.path)


class LoopDevice(StorageDevice):
    """ A loop device. """
    _type = "loop"

    def __init__(self, name=None, format=None, size=None, sysfsPath=None,
                 exists=False, parents=None):
        """ Create a LoopDevice instance.

            Arguments:

                name -- the device's name

            Keyword Arguments:

                format -- a DeviceFormat instance
                size -- the device's size in MB
                parents -- a list of required devices (Device instances)
                exists -- indicates whether this is an existing device


            Loop devices always exist.
        """
        if not parents:
            raise ValueError("LoopDevice requires a backing device")

        if not name:
            # set up a temporary name until we've activated the loop device
            name = "tmploop%d" % Device._id

        StorageDevice.__init__(self, name, format=format, size=size,
                               exists=True, parents=parents)

    def updateName(self):
        """ Update this device's name. """
        if not self.slave.status:
            # if the backing device is inactive, so are we
            return self.name

        if self.name.startswith("loop"):
            # if our name is loopN we must already be active
            return self.name

        name = loop.get_loop_name(self.slave.path)
        if name.startswith("loop"):
            self._name = name

        return self.name

    @property
    def status(self):
        return (self.slave.status and
                self.name.startswith("loop") and
                loop.get_loop_name(self.slave.path) == self.name)

    @property
    def size(self):
        return self.slave.size

    def _setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)
        loop.loop_setup(self.slave.path)

    def _postSetup(self):
        StorageDevice._postSetup(self)
        self.updateName()
        self.updateSysfsPath()

    def _teardown(self, recursive=False):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)
        loop.loop_teardown(self.path)

    def _postTeardown(self, recursive=False):
        StorageDevice._postTeardown(self, recursive=recursive)
        self._name = "tmploop%d" % self.id
        self.sysfsPath = ''

    @property
    def slave(self):
        return self.parents[0]


class iScsiDiskDevice(DiskDevice, NetworkStorageDevice):
    """ An iSCSI disk. """
    _type = "iscsi"
    _packages = ["iscsi-initiator-utils", "dracut-network"]

    def __init__(self, device, **kwargs):
        self.node = kwargs.pop("node")
        self.ibft = kwargs.pop("ibft")
        self.nic = kwargs.pop("nic")
        self.initiator = kwargs.pop("initiator")

        if self.node is None:
            # qla4xxx partial offload
            name = kwargs.pop("fw_name")
            address = kwargs.pop("fw_address")
            port = kwargs.pop("fw_port")
            DiskDevice.__init__(self, device, **kwargs)
            NetworkStorageDevice.__init__(self,
                                          host_address=address,
                                          nic=self.nic)
            log.debug("created new iscsi disk %s %s:%s using fw initiator %s"
                      % (name, address, port, self.initiator))
        else:
            DiskDevice.__init__(self, device, **kwargs)
            NetworkStorageDevice.__init__(self, host_address=self.node.address,
                                          nic=self.nic)
            log.debug("created new iscsi disk %s %s:%d via %s:%s" % (self.node.name,
                                                                  self.node.address,
                                                                  self.node.port,
                                                                  self.node.iface,
                                                                  self.nic))

    def dracutSetupArgs(self):
        if self.ibft:
            return set(["iscsi_firmware"])

        # qla4xxx partial offload
        if self.node is None:
            return set()

        address = self.node.address
        # surround ipv6 addresses with []
        if ":" in address:
            address = "[%s]" % address

        netroot="netroot=iscsi:"
        auth = self.node.getAuth()
        if auth:
            netroot += "%s:%s" % (auth.username, auth.password)
            if len(auth.reverse_username) or len(auth.reverse_password):
                netroot += ":%s:%s" % (auth.reverse_username,
                                       auth.reverse_password)

        iface_spec = ""
        if self.nic != "default":
            iface_spec = ":%s:%s" % (self.node.iface, self.nic)
        netroot += "@%s::%d%s::%s" % (address,
                                      self.node.port,
                                      iface_spec,
                                      self.node.name)

        initiator = "iscsi_initiator=%s" % self.initiator

        return set([netroot, initiator])

class FcoeDiskDevice(DiskDevice, NetworkStorageDevice):
    """ An FCoE disk. """
    _type = "fcoe"
    _packages = ["fcoe-utils", "dracut-network"]

    def __init__(self, device, **kwargs):
        self.nic = kwargs.pop("nic")
        self.identifier = kwargs.pop("identifier")
        DiskDevice.__init__(self, device, **kwargs)
        NetworkStorageDevice.__init__(self, nic=self.nic)
        log.debug("created new fcoe disk %s (%s) @ %s" %
                  (device, self.identifier, self.nic))

    def dracutSetupArgs(self):
        dcb = True

        from .fcoe import fcoe
        for nic, dcb, auto_vlan in fcoe().nics:
            if nic == self.nic:
                break

        if dcb:
            dcbOpt = "dcb"
        else:
            dcbOpt = "nodcb"

        return set(["fcoe=edd:%s" % dcbOpt])


class OpticalDevice(StorageDevice):
    """ An optical drive, eg: cdrom, dvd+r, &c.

        XXX Is this useful?
    """
    _type = "cdrom"

    def __init__(self, name, major=None, minor=None, exists=False,
                 format=None, parents=None, sysfsPath='', vendor="",
                 model=""):
        StorageDevice.__init__(self, name, format=format,
                               major=major, minor=minor, exists=True,
                               parents=parents, sysfsPath=sysfsPath,
                               vendor=vendor, model=model)

    @property
    def mediaPresent(self):
        """ Return a boolean indicating whether or not the device contains
            media.
        """
        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

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
        from pyanaconda import _isys

        log_method_call(self, self.name, status=self.status)
        if not self.exists:
            raise DeviceError("device has not been created", self.name)

        #try to umount and close device before ejecting
        self.teardown()

        if flags.cmdline.has_key('noeject'):
            log.info("noeject in effect, not ejecting cdrom")
            return

        # Make a best effort attempt to do the eject.  If it fails, it's not
        # critical.
        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)

        try:
            _isys.ejectcdrom(fd)
        except SystemError as e:
            log.warning("error ejecting cdrom %s: %s" % (self.name, e))

        os.close(fd)


class ZFCPDiskDevice(DiskDevice):
    """ A mainframe ZFCP disk. """
    _type = "zfcp"

    def __init__(self, device, **kwargs):
        self.hba_id = kwargs.pop("hba_id")
        self.wwpn = kwargs.pop("wwpn")
        self.fcp_lun = kwargs.pop("fcp_lun")
        DiskDevice.__init__(self, device, **kwargs)

    def __repr__(self):
        s = DiskDevice.__repr__(self)
        s += ("  hba_id = %(hba_id)s  wwpn = %(wwpn)s  fcp_lun = %(fcp_lun)s" %
              {"hba_id": self.hba_id,
               "wwpn": self.wwpn,
               "fcp_lun": self.fcp_lun})
        return s

    @property
    def description(self):
        return "FCP device %(device)s with WWPN %(wwpn)s and LUN %(lun)s" \
               % {'device': self.hba_id,
                  'wwpn': self.wwpn,
                  'lun': self.fcp_lun}

    def dracutSetupArgs(self):
        return set(["rd.zfcp=%s,%s,%s" % (self.hba_id, self.wwpn, self.fcp_lun,)])

class DASDDevice(DiskDevice):
    """ A mainframe DASD. """
    _type = "dasd"

    def __init__(self, device, **kwargs):
        self.busid = kwargs.pop('busid')
        self.opts = kwargs.pop('opts')
        self.dasd = kwargs.pop('dasd')
        DiskDevice.__init__(self, device, **kwargs)

        if self.dasd:
            self.dasd.addDASD(self)

    @property
    def description(self):
        return "DASD device %s" % self.busid

    def getOpts(self):
        return ["%s=%s" % (k, v) for k, v in self.opts.items() if v == '1']

    def dracutSetupArgs(self):
        conf = "/etc/dasd.conf"
        line = None
        if os.path.isfile(conf):
            f = open(conf)
            # grab the first line that starts with our busID
            line = [line for line in f.readlines()
                    if line.startswith(self.busid)][:1]
            f.close()

        # See if we got a line.  If not, grab our getOpts
        if not line:
            line = self.busid
            for devopt in self.getOpts():
                line += " %s" % devopt

        # Create a translation mapping from dasd.conf format to module format
        translate = {'use_diag': 'diag',
                     'readonly': 'ro',
                     'erplog': 'erplog',
                     'failfast': 'failfast'}

        # this is a really awkward way of determining if the
        # feature found is actually desired (1, not 0), plus
        # translating that feature into the actual kernel module
        # value
        opts = []
        parts = line.split()
        for chunk in parts[1:]:
            try:
                feat, val = chunk.split('=')
                if int(val):
                    opts.append(translate[feat])
            except:
                # If we don't know what the feature is (feat not in translate
                # or if we get a val that doesn't cleanly convert to an int
                # we can't do anything with it.
                log.warning("failed to parse dasd feature %s" % chunk)

        if opts:
            return set(["rd.dasd=%s(%s)" % (self.busid,
                                            ":".join(opts))])
        else:
            return set(["rd.dasd=%s" % self.busid])

class NFSDevice(StorageDevice, NetworkStorageDevice):
    """ An NFS device """
    _type = "nfs"
    _packages = ["dracut-network"]

    def __init__(self, device, format=None, parents=None):
        # we could make host/ip, path, &c but will anything use it?
        StorageDevice.__init__(self, device, format=format, parents=parents)
        NetworkStorageDevice.__init__(self, device.split(":")[0])

    @property
    def path(self):
        """ Device node representing this device. """
        return self.name

    def setup(self, orig=False):
        """ Open, or set up, a device. """
        log_method_call(self, self.name, orig=orig, status=self.status,
                        controllable=self.controllable)

    def teardown(self, recursive=None):
        """ Close, or tear down, a device. """
        log_method_call(self, self.name, status=self.status,
                        controllable=self.controllable)

    def create(self):
        """ Create the device. """
        log_method_call(self, self.name, status=self.status)
        self._preCreate()

    def destroy(self):
        """ Destroy the device. """
        log_method_call(self, self.name, status=self.status)


class BTRFSDevice(StorageDevice):
    """ Base class for BTRFS volume and sub-volume devices. """
    _type = "btrfs"
    _packages = ["btrfs-progs"]

    def __init__(self, *args, **kwargs):
        """ Passing None or no name means auto-generate one like btrfs.%d """
        if not args or not args[0]:
            args = ("btrfs.%d" % Device._id,)

        self.req_size = kwargs.pop("size", None)
        super(BTRFSDevice, self).__init__(*args, **kwargs)

    def updateSysfsPath(self):
        """ Update this device's sysfs path. """
        log_method_call(self, self.name, status=self.status)
        self.parents[0].updateSysfsPath()
        self.sysfsPath = self.parents[0].sysfsPath
        log.debug("%s sysfsPath set to %s" % (self.name, self.sysfsPath))

    def _postCreate(self):
        super(BTRFSDevice, self)._postCreate()
        self.format.exists = True
        self.format.device = self.path

    def _preDestroy(self):
        """ Preparation and precondition checking for device destruction. """
        super(BTRFSDevice, self)._preDestroy()
        self.setupParents(orig=True)

    def _getSize(self):
        size = sum([d.size for d in self.parents])
        return size

    def _setSize(self, size):
        raise RuntimeError("cannot directly set size of btrfs volume")

    @property
    def status(self):
        return not any([not d.status for d in self.parents])

    @property
    def _temp_dir_prefix(self):
        return "btrfs-tmp.%s" % self.id

    def _do_temp_mount(self, orig=False):
        if self.format.status or not self.exists:
            return

        tmpdir = tempfile.mkdtemp(prefix=self._temp_dir_prefix)
        if orig:
            fmt = self.originalFormat
        else:
            fmt = self.format

        fmt.mount(mountpoint=tmpdir)

    def _undo_temp_mount(self):
        if getattr(self.format, "_mountpoint", None):
            fmt = self.format
        elif getattr(self.originalFormat, "_mountpoint", None):
            fmt = self.originalFormat
        else:
            return

        mountpoint = fmt._mountpoint

        if os.path.basename(mountpoint).startswith(self._temp_dir_prefix):
            fmt.unmount()
            os.rmdir(mountpoint)

    @property
    def path(self):
        return self.parents[0].path


class BTRFSVolumeDevice(BTRFSDevice):
    _type = "btrfs volume"

    def __init__(self, *args, **kwargs):
        self.dataLevel = kwargs.pop("dataLevel", None)
        self.metaDataLevel = kwargs.pop("metaDataLevel", None)

        super(BTRFSVolumeDevice, self).__init__(*args, **kwargs)

        self.subvolumes = []

        for parent in self.parents:
            if parent.format.type != "btrfs":
                raise ValueError("member device %s is not BTRFS" % parent.name)

            if parent.format.exists and self.exists and \
               parent.format.volUUID != self.uuid:
                raise ValueError("BTRFS member device %s UUID %s does not "
                                 "match volume UUID %s" % (parent.name,
                                 parent.format.volUUID, self.uuid))

        if self.parents and not self.format.type:
            label = getattr(self.parents[0].format, "label", None)
            self.format = getFormat("btrfs",
                                    exists=self.exists,
                                    label=label,
                                    volUUID=self.uuid,
                                    device=self.path)
            self.originalFormat = copy.copy(self.format)

    def _setFormat(self, format):
        """ Set the Device's format. """
        super(BTRFSVolumeDevice, self)._setFormat(format)
        self._name = "btrfs.%d" % self.id
        label = getattr(self.format, "label", None)
        if label:
            self._name = label

    def _getSize(self):
        size = sum([d.size for d in self.parents])
        if self.dataLevel in ("raid1", "raid10"):
            size /= len(self.parents)

        return size

    def _addDevice(self, device):
        """ Add a new device to this volume.

            XXX This is for use by device probing routines and is not
                intended for modification of the volume.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)
        if not self.exists:
            raise DeviceError("device does not exist", self.name)

        if device.format.type != "btrfs":
            raise ValueError("addDevice requires a btrfs device as sole arg")

        if device.format.volUUID != self.uuid:
            raise ValueError("device UUID does not match the volume UUID")

        if device in self.parents:
            raise ValueError("device is already a member of this volume")

        self.parents.append(device)
        device.addChild()

    def _removeDevice(self, device):
        """ Remove a device from the volume.

            This is for cases like clearing of preexisting partitions.
        """
        log_method_call(self,
                        self.name,
                        device=device.name,
                        status=self.status)
        try:
            self.parents.remove(device)
        except ValueError:
            raise ValueError("cannot remove non-member device from volume")

        device.removeChild()

    def addMember(self, member):
        if member in self.parents:
            raise ValueError("member is already part of this volume")

        # for the time being we will not allow adding members to existing vols
        if self.exists:
            raise DeviceError("cannot add member to existing volume", self.name)

        self.parents.append(member)
        member.addChild()

    def removeMember(self, member):
        if member not in self.parents:
            raise ValueError("member is not part of this volume")

        if self.exists:
            raise DeviceError("cannot remove member from an existing volume")

        self.parents.remove(member)
        member.removeChild()

    def _addSubVolume(self, vol):
        if vol.name in [v.name for v in self.subvolumes]:
            raise ValueError("subvolume %s already exists" % vol.name)

        self.subvolumes.append(vol)

    def _removeSubVolume(self, name):
        if name not in [v.name for v in self.subvolumes]:
            raise ValueError("cannot remove non-existent subvolume %s" % name)

        names = [v.name for v in self.subvolumes]
        self.subvolumes.pop(names.index(name))

    def listSubVolumes(self):
        subvols = []
        self.setup(orig=True)
        try:
            self._do_temp_mount(orig=True)
        except FSError as e:
            log.debug("btrfs temp mount failed: %s" % e)
            return subvols

        try:
            subvols = btrfs.list_subvolumes(self.originalFormat._mountpoint)
        except BTRFSError as e:
            log.debug("failed to list subvolumes: %s" % e)
        finally:
            self._undo_temp_mount()

        return subvols

    def createSubVolumes(self):
        self._do_temp_mount()
        for name, subvol in self.subvolumes:
            if subvol.exists:
                continue
            subvol.create(mountpoint=self._temp_dir_prefix)
        self._undo_temp_mount()

    def removeSubVolume(self, name):
        raise NotImplementedError()

    def _create(self):
        log_method_call(self, self.name, status=self.status)
        btrfs.create_volume(devices=[d.path for d in self.parents],
                            label=self.format.label,
                            data=self.dataLevel,
                            metadata=self.metaDataLevel)

    def _destroy(self):
        log_method_call(self, self.name, status=self.status)
        for device in self.parents:
            device.setup(orig=True)
            DeviceFormat(device=device.path, exists=True).destroy()

class BTRFSSubVolumeDevice(BTRFSDevice):
    """ A btrfs subvolume pseudo-device. """
    _type = "btrfs subvolume"

    def __init__(self, *args, **kwargs):
        self.vol_id = kwargs.pop("vol_id", None)
        super(BTRFSSubVolumeDevice, self).__init__(*args, **kwargs)

        self.volume._addSubVolume(self)

    @property
    def volume(self):
        return self.parents[0]

    def setupParents(self, orig=False):
        """ Run setup method of all parent devices. """
        log_method_call(self, name=self.name, orig=orig, kids=self.kids)
        self.volume.setup(orig=orig)

    def _create(self):
        log_method_call(self, self.name, status=self.status)
        self.volume._do_temp_mount()
        mountpoint = self.volume.format._mountpoint
        if not mountpoint:
            raise RuntimeError("btrfs subvol create requires mounted volume")

        btrfs.create_subvolume(mountpoint, self.name)
        self.volume._undo_temp_mount()

    def _destroy(self):
        log_method_call(self, self.name, status=self.status)
        self.volume._do_temp_mount(orig=True)
        mountpoint = self.volume.originalFormat._mountpoint
        if not mountpoint:
            raise RuntimeError("btrfs subvol destroy requires mounted volume")
        btrfs.delete_subvolume(mountpoint, self.name)
        self.volume._undo_temp_mount()
