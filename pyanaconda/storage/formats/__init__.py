# __init__.py
# Entry point for anaconda storage formats subpackage.
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

from pyanaconda.baseudev import udev_get_device
from pyanaconda.iutil import notify_kernel
from pyanaconda.iutil import get_sysfs_path_by_name
from pyanaconda.iutil import execWithRedirect
from pyanaconda.anaconda_log import log_method_call
from ..errors import *
from ..devicelibs.dm import dm_node_from_name
from ..devicelibs.mdraid import md_node_from_name
from ..udev import udev_device_get_major, udev_device_get_minor

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


device_formats = {}
def register_device_format(fmt_class):
    if not issubclass(fmt_class, DeviceFormat):
        raise ValueError("arg1 must be a subclass of DeviceFormat")

    device_formats[fmt_class._type] = fmt_class
    log.debug("registered device format class %s as %s" % (fmt_class.__name__,
                                                           fmt_class._type))

default_fstypes = ("ext4", "ext3", "ext2")
def get_default_filesystem_type():
    for fstype in default_fstypes:
        try:
            supported = get_device_format_class(fstype).supported
        except AttributeError:
            supported = None

        if supported:
            return fstype

    raise DeviceFormatError("None of %s is supported by your kernel" % ",".join(default_fstypes))

def getFormat(fmt_type, *args, **kwargs):
    """ Return a DeviceFormat instance based on fmt_type and args.

        Given a device format type and a set of constructor arguments,
        return a DeviceFormat instance.

        Return None if no suitable format class is found.

        Arguments:

            fmt_type -- the name of the format type (eg: 'ext3', 'swap')

        Keyword Arguments:

            The keyword arguments may vary according to the format type,
            but here is the common set:

            device -- path to the device on which the format resides
            uuid -- the UUID of the (preexisting) formatted device
            exists -- whether or not the format exists on the device            
            
    """
    fmt_class = get_device_format_class(fmt_type)
    fmt = None
    if fmt_class:
        fmt = fmt_class(*args, **kwargs)
    try:
        className = fmt.__class__.__name__
    except AttributeError:
        className = None
    log.debug("getFormat('%s') returning %s instance" % (fmt_type, className))
    return fmt

def collect_device_format_classes():
    """ Pick up all device format classes from this directory.

        Note: Modules must call register_device_format(FormatClass) in
              order for the format class to be picked up.
    """
    dir = os.path.dirname(__file__)
    for module_file in os.listdir(dir):
        # make sure we're not importing this module
        if module_file.endswith(".py") and module_file != __file__:
            mod_name = module_file[:-3]
            # imputil is deprecated in python 2.6
            try:
                globals()[mod_name] = __import__(mod_name, globals(), locals(), [], -1)
            except ImportError:
                log.error("import of device format module '%s' failed" % mod_name)
                from traceback import format_exc
                log.debug(format_exc())

def get_device_format_class(fmt_type):
    """ Return an appropriate format class based on fmt_type. """
    if not device_formats:
        collect_device_format_classes()

    fmt = device_formats.get(fmt_type)
    if not fmt:
        for fmt_class in device_formats.values():
            if fmt_type and fmt_type == fmt_class._name:
                fmt = fmt_class
                break
            elif fmt_type in fmt_class._udevTypes:
                fmt = fmt_class
                break

    # default to no formatting, AKA "Unknown"
    if not fmt:
        fmt = DeviceFormat

    return fmt

class DeviceFormat(object):
    """ Generic device format. """
    _type = None
    _name = "Unknown"
    _udevTypes = []
    partedFlag = None
    partedSystem = None
    _formattable = False                # can be formatted
    _supported = False                  # is supported
    _linuxNative = False                # for clearpart
    _packages = []                      # required packages
    _services = []                      # required services
    _resizable = False                  # can be resized
    _migratable = False                 # can be migrated
    _maxSize = 0                        # maximum size in MB
    _minSize = 0                        # minimum size in MB
    _dump = False
    _check = False
    _hidden = False                     # hide devices with this formatting?

    def __init__(self, *args, **kwargs):
        """ Create a DeviceFormat instance.

            Keyword Arguments:

                device -- path to the underlying device
                uuid -- this format's UUID
                exists -- indicates whether this is an existing format

        """
        self.device = kwargs.get("device")
        self.uuid = kwargs.get("uuid")
        self.exists = kwargs.get("exists")
        self.options = kwargs.get("options")
        self._majorminor = None
        self._migrate = False

        # don't worry about existence if this is a DeviceFormat instance
        #if self.__class__ is DeviceFormat:
        #    self.exists = True

    def __repr__(self):
        s = ("%(classname)s instance (%(id)s) --\n"
             "  type = %(type)s  name = %(name)s  status = %(status)s\n"
             "  device = %(device)s  uuid = %(uuid)s  exists = %(exists)s\n"
             "  options = %(options)s  supported = %(supported)s"
             "  formattable = %(format)s  resizable = %(resize)s\n" %
             {"classname": self.__class__.__name__, "id": "%#x" % id(self),
              "type": self.type, "name": self.name, "status": self.status,
              "device": self.device, "uuid": self.uuid, "exists": self.exists,
              "options": self.options, "supported": self.supported,
              "format": self.formattable, "resize": self.resizable})
        return s

    @property
    def _existence_str(self):
        exist = "existing"
        if not self.exists:
            exist = "non-existent"
        return exist

    @property
    def desc(self):
        return str(self.type)

    def __str__(self):
        return "%s %s" % (self._existence_str, self.desc)

    @property
    def dict(self):
        d = {"type": self.type, "name": self.name, "device": self.device,
             "uuid": self.uuid, "exists": self.exists,
             "options": self.options, "supported": self.supported,
             "resizable": self.resizable}
        return d

    def _setOptions(self, options):
        self._options = options

    def _getOptions(self):
        return self._options

    options = property(_getOptions, _setOptions)

    def _setDevice(self, devspec):
        if devspec and not devspec.startswith("/"):
            raise ValueError("device must be a fully qualified path")
        self._device = devspec

    def _getDevice(self):
        return self._device

    device = property(lambda f: f._getDevice(),
                      lambda f,d: f._setDevice(d),
                      doc="Full path the device this format occupies")

    @property
    def name(self):
        if self._name:
            name = self._name
        else:
            name = self.type
        return name

    @property
    def type(self):
        return self._type

    def probe(self):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)

    def notifyKernel(self):
        log_method_call(self, device=self.device,
                        type=self.type)
        if not self.device:
            return

        if self.device.startswith("/dev/mapper/"):
            try:
                name = dm_node_from_name(os.path.basename(self.device))
            except DMError:
                log.warning("failed to get dm node for %s" % self.device)
                return
        elif self.device.startswith("/dev/md/"):
            try:
                name = md_node_from_name(os.path.basename(self.device))
            except MDRaidError:
                log.warning("failed to get md node for %s" % self.device)
                return
        else:
            name = self.device

        path = get_sysfs_path_by_name(name)
        try:
            notify_kernel(path, action="change")
        except (ValueError, IOError) as e:
            log.warning("failed to notify kernel of change: %s" % e)

    def cacheMajorminor(self):
        """ Cache the value of self.majorminor.

            Once a device node of this format's device disappears (for instance
            after a teardown), it is no longer possible to figure out the value
            of self.majorminor pseudo-unique string. Call this method before
            that happens for caching this.
        """
        self._majorminor = None
        try:
            self.majorminor # this does the caching
        except StorageError:
            # entirely possible there's no majorminor, for instance an
            # LVMVolumeGroup has got no device node and no sysfs path.  In this
            # case obviously, calling majorminor of this object later raises an
            # exception.
            pass
        return self._majorminor

    def create(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        # allow late specification of device path
        device = kwargs.get("device")
        if device:
            self.device = device

        if not os.path.exists(self.device):
            raise FormatCreateError("invalid device specification", self.device)

    def destroy(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)
        try:
            rc = execWithRedirect("wipefs", ["-a", self.device],
                                  stderr="/dev/tty5",
                                  stdout="/dev/tty5")
        except Exception as e:
            err = str(e)
        else:
            err = ""
            if rc:
                err = str(rc)

        if err:
            msg = "error wiping old signatures from %s: %s" % (self.device, err)
            raise FormatDestroyError(msg)

        self.exists = False

    def setup(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)

        if not self.exists:
            raise FormatSetupError("format has not been created")

        if self.status:
            return

        # allow late specification of device path
        device = kwargs.get("device")
        if device:
            self.device = device

        if not self.device or not os.path.exists(self.device):
            raise FormatSetupError("invalid device specification")

    def teardown(self, *args, **kwargs):
        log_method_call(self, device=self.device,
                        type=self.type, status=self.status)

    @property
    def status(self):
        return (self.exists and
                self.__class__ is not DeviceFormat and
                isinstance(self.device, str) and
                self.device and 
                os.path.exists(self.device))

    @property
    def formattable(self):
        """ Can we create formats of this type? """
        return self._formattable

    @property
    def supported(self):
        """ Is this format a supported type? """
        return self._supported

    @property
    def packages(self):
        """ Packages required to manage formats of this type. """
        return self._packages

    @property
    def services(self):
        """ Services required to manage formats of this type. """
        return self._services

    @property
    def resizable(self):
        """ Can formats of this type be resized? """
        return self._resizable and self.exists

    @property
    def migratable(self):
        """ Can formats of this type be migrated? """
        return self._migratable

    @property
    def migrate(self):
        return self._migrate

    @property
    def linuxNative(self):
        """ Is this format type native to linux? """
        return self._linuxNative

    @property
    def mountable(self):
        """ Is this something we can mount? """
        return False

    @property
    def dump(self):
        """ Whether or not this format will be dumped by dump(8). """
        return self._dump

    @property
    def check(self):
        """ Whether or not this format is checked on boot. """
        return self._check

    @property
    def maxSize(self):
        """ Maximum size (in MB) for this format type. """
        return self._maxSize

    @property
    def minSize(self):
        """ Minimum size (in MB) for this format type. """
        return self._minSize

    @property
    def hidden(self):
        """ Whether devices with this formatting should be hidden in UIs. """
        return self._hidden

    @property
    def majorminor(self):
        """A string suitable for using as a pseudo-unique ID in kickstart."""
        if not self._majorminor:
            # If this is a device-mapper device, we have to get the DM node and
            # build the sysfs path from that.
            try:
                device = dm_node_from_name(os.path.basename(self.device))
            except DMError:
                device = self.device

            try:
                sysfs_path = get_sysfs_path_by_name(device)
            except RuntimeError:
                raise StorageError("DeviceFormat.majorminor: "
                                   "can not get majorminor for '%s'" % device)
            dev = udev_get_device(sysfs_path[4:])

            self._majorminor = "%03d%03d" %\
                (udev_device_get_major(dev), udev_device_get_minor(dev))
        return self._majorminor

collect_device_format_classes()
