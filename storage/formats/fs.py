# filesystems.py
# Filesystem classes for anaconda's storage configuration module.
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
#                    David Cantrell <dcantrell@redhat.com>
#

""" Filesystem classes for use by anaconda.

    TODO:
        - migration
        - bug 472127: allow creation of tmpfs filesystems (/tmp, /var/tmp, &c)
"""
import math
import os
import sys
import tempfile
import selinux
import isys

from ..errors import *
from . import DeviceFormat, register_device_format
import iutil
from flags import flags
from parted import fileSystemType
from ..storage_log import log_method_call

import logging
log = logging.getLogger("storage")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

try:
    lost_and_found_context = selinux.matchpathcon("/lost+found", 0)[1]
except OSError:
    lost_and_found_context = None

fs_configs = {}

def get_kernel_filesystems():
    fs_list = []
    for line in open("/proc/filesystems").readlines():
        fs_list.append(line.split()[-1])
    return fs_list

global kernel_filesystems
kernel_filesystems = get_kernel_filesystems()

def fsConfigFromFile(config_file):
    """ Generate a set of attribute name/value pairs with which a
        filesystem type can be defined.

        The following config file would define a filesystem identical to
        the static Ext3FS class definition:

            type = ext3
            mkfs = "mke2fs"
            resizefs = "resize2fs"
            labelfs = "e2label"
            fsck = "e2fsck"
            packages = ["e2fsprogs"]
            formattable = True
            supported = True
            resizable = True
            bootable = True
            linuxNative = True
            maxSize = 8 * 1024 * 1024
            minSize = 0
            defaultFormatOptions = "-t ext3"
            defaultMountOptions = "defaults"

    """
    # XXX NOTUSED
    lines = open(config_file).readlines()
    fs_attrs = {}
    for line in lines:
        (key, value) = [t.strip() for t in line.split("=")]
        if not hasattr(FS, "_" + key):
            print "invalid key: %s" % key
            continue

        fs_attrs[key] = value

    if not fs_attrs.has_key("type"):
        raise ValueError, _("filesystem configuration missing a type")

    # XXX what's the policy about multiple configs for a given type?
    fs_configs[fs_attrs['type']] = fs_attrs

class FS(DeviceFormat):
    """ Filesystem class. """
    _type = "Abstract Filesystem Class"  # fs type name
    _mountType = None                    # like _type but for passing to mount
    _name = None
    _mkfs = ""                           # mkfs utility
    _modules = []                        # kernel modules required for support
    _resizefs = ""                       # resize utility
    _labelfs = ""                        # labeling utility
    _fsck = ""                           # fs check utility
    _fsckErrors = {}                     # fs check command error codes & msgs
    _migratefs = ""                      # fs migration utility
    _infofs = ""                         # fs info utility
    _defaultFormatOptions = []           # default options passed to mkfs
    _defaultMountOptions = ["defaults"]  # default options passed to mount
    _defaultLabelOptions = []
    _defaultCheckOptions = []
    _defaultMigrateOptions = []
    _defaultInfoOptions = []
    _migrationTarget = None
    _existingSizeFields = []
    _fsProfileSpecifier = None           # mkfs option specifying fsprofile

    def __init__(self, *args, **kwargs):
        """ Create a FS instance.

            Keyword Args:

                device -- path to the device containing the filesystem
                mountpoint -- the filesystem's mountpoint
                label -- the filesystem label
                uuid -- the filesystem UUID
                mountopts -- mount options for the filesystem
                size -- the filesystem's size in MiB
                exists -- indicates whether this is an existing filesystem
                
        """
        if self.__class__ is FS:
            raise TypeError("FS is an abstract class.")

        DeviceFormat.__init__(self, *args, **kwargs)
        self.mountpoint = kwargs.get("mountpoint")
        self.mountopts = kwargs.get("mountopts")
        self.label = kwargs.get("label")
        self.fsprofile = kwargs.get("fsprofile")

        # filesystem size does not necessarily equal device size
        self._size = kwargs.get("size", 0)
        self._minInstanceSize = None    # min size of this FS instance
        self._mountpoint = None     # the current mountpoint when mounted
        if self.exists and self.supported:
            self._size = self._getExistingSize()
            foo = self.minSize      # force calculation of minimum size

        self._targetSize = self._size

        if self.supported:
            self.loadModule()

    def __str__(self):
        s = DeviceFormat.__str__(self)
        s += ("  mountpoint = %(mountpoint)s  mountopts = %(mountopts)s\n"
              "  label = %(label)s  size = %(size)s"
              "  targetSize = %(targetSize)s\n" %
              {"mountpoint": self.mountpoint, "mountopts": self.mountopts,
               "label": self.label, "size": self._size,
               "targetSize": self.targetSize})
        return s

    @property
    def dict(self):
        d = super(FS, self).dict
        d.update({"mountpoint": self.mountpoint, "size": self._size,
                  "label": self.label, "targetSize": self.targetSize,
                  "mountable": self.mountable,
                  "migratable": self.migratable})
        return d

    def _setTargetSize(self, newsize):
        """ Set a target size for this filesystem. """
        if not self.exists:
            raise FSError("filesystem has not been created")

        if newsize is None:
            # unset any outstanding resize request
            self._targetSize = None
            return

        if not self.minSize <= newsize < self.maxSize:
            raise ValueError("invalid target size request")

        self._targetSize = newsize

    def _getTargetSize(self):
        """ Get this filesystem's target size. """
        return self._targetSize

    targetSize = property(_getTargetSize, _setTargetSize,
                          doc="Target size for this filesystem")

    def _getSize(self):
        """ Get this filesystem's size. """
        size = self._size
        if self.resizable and self.targetSize != size:
            size = self.targetSize
        return size

    size = property(_getSize, doc="This filesystem's size, accounting "
                                  "for pending changes")

    def _getExistingSize(self):
        """ Determine the size of this filesystem.  Filesystem must
            exist.  Each filesystem varies, but the general procedure
            is to run the filesystem dump or info utility and read
            the block size and number of blocks for the filesystem
            and compute megabytes from that.

            The loop that reads the output from the infofsProg is meant
            to be simple, but take in to account variations in output.
            The general procedure:
                1) Capture output from infofsProg.
                2) Iterate over each line of the output:
                       a) Trim leading and trailing whitespace.
                       b) Break line into fields split on ' '
                       c) If line begins with any of the strings in
                          _existingSizeFields, start at the end of
                          fields and take the first one that converts
                          to a long.  Store this in the values list.
                       d) Repeat until the values list length equals
                          the _existingSizeFields length.
                3) If the length of the values list equals the length
                   of _existingSizeFields, compute the size of this
                   filesystem by multiplying all of the values together
                   to get bytes, then convert to megabytes.  Return
                   this value.
                4) If we were unable to capture all fields, return 0.

            The caller should catch exceptions from this method.  Any
            exception raised indicates a need to change the fields we
            are looking for, the command to run and arguments, or
            something else.  If you catch an exception from this method,
            assume the filesystem cannot be resized.
        """
        size = self._size

        if self.infofsProg and self.mountable and self.exists and not size:
            try:
                values = []
                argv = self._defaultInfoOptions + [ self.device ]

                buf = iutil.execWithCapture(self.infofsProg, argv,
                                            stderr="/dev/tty5")

                for line in buf.splitlines():
                    found = False

                    line = line.strip()
                    tmp = line.split(' ')
                    tmp.reverse()

                    for field in self._existingSizeFields:
                        if line.startswith(field):
                            for subfield in tmp:
                                try:
                                    values.append(long(subfield))
                                    found = True
                                    break
                                except ValueError:
                                    continue

                        if found:
                            break

                    if len(values) == len(self._existingSizeFields):
                        break

                if len(values) != len(self._existingSizeFields):
                    return 0

                size = 1
                for value in values:
                    size *= value

                # report current size as megabytes
                size = math.floor(size / 1024.0 / 1024.0)
            except Exception as e:
                log.error("failed to obtain size of filesystem on %s: %s"
                          % (self.device, e))

        return size

    @property
    def currentSize(self):
        """ The filesystem's current actual size. """
        size = 0
        if self.exists:
            size = self._size
        return float(size)

    def _getFormatOptions(self, options=None):
        argv = []
        if options and isinstance(options, list):
            argv.extend(options)
        argv.extend(self.defaultFormatOptions)
        if self._fsProfileSpecifier and self.fsprofile:
            argv.extend([self._fsProfileSpecifier, self.fsprofile])
        argv.append(self.device)
        return argv
    
    def doFormat(self, *args, **kwargs):
        """ Create the filesystem.

            Arguments:

                None

            Keyword Arguments:

                intf -- InstallInterface instance
                options -- list of options to pass to mkfs

        """
        log_method_call(self, type=self.mountType, device=self.device,
                        mountpoint=self.mountpoint)

        intf = kwargs.get("intf")
        options = kwargs.get("options")

        if self.exists:
            raise FormatCreateError("filesystem already exists", self.device)

        if not self.formattable:
            return

        if not self.mkfsProg:
            return

        if self.exists:
            return

        if not os.path.exists(self.device):
            raise FormatCreateError("device does not exist", self.device)

        argv = self._getFormatOptions(options=options)

        w = None
        if intf:
            w = intf.progressWindow(_("Formatting"),
                                    _("Creating %s filesystem on %s")
                                    % (self.type, self.device),
                                    100, pulse = True)

        try:
            rc = iutil.execWithPulseProgress(self.mkfsProg,
                                             argv,
                                             stdout="/dev/tty5",
                                             stderr="/dev/tty5",
                                             progress=w)
        except Exception as e:
            raise FormatCreateError(e, self.device)
        finally:
            if w:
                w.pop()

        if rc:
            raise FormatCreateError("format failed: %s" % rc, self.device)

        self.exists = True
        self.notifyKernel()

        if self.label:
            self.writeLabel(self.label)

    def doMigrate(self, intf=None):
        if not self.exists:
            raise FSError("filesystem has not been created")

        if not self.migratable or not self.migrate:
            return

        if not os.path.exists(self.device):
            raise FSError("device does not exist")

        # if journal already exists skip
        if isys.ext2HasJournal(self.device):
            log.info("Skipping migration of %s, has a journal already."
                     % self.device)
            return

        argv = self._defaultMigrateOptions[:]
        argv.append(self.device)
        try:
            rc = iutil.execWithRedirect(self.migratefsProg,
                                        argv,
                                        stdout = "/dev/tty5",
                                        stderr = "/dev/tty5")
        except Exception as e:
            raise FSMigrateError("filesystem migration failed: %s" % e,
                                 self.device)

        if rc:
            raise FSMigrateError("filesystem migration failed: %s" % rc,
                                 self.device)

        # the other option is to actually replace this instance with an
        # instance of the new filesystem type.
        self._type = self.migrationTarget

    @property
    def resizeArgs(self):
        argv = [self.device, "%d" % (self.targetSize,)]
        return argv

    def doResize(self, *args, **kwargs):
        """ Resize this filesystem to new size @newsize.

            Arguments:

                None

            Keyword Arguments:

                intf -- InstallInterface instance

        """
        intf = kwargs.get("intf")

        if not self.exists:
            raise FSResizeError("filesystem does not exist", self.device)

        if not self.resizable:
            raise FSResizeError("filesystem not resizable", self.device)

        if self.targetSize == self.currentSize:
            return

        if not self.resizefsProg:
            return

        if not os.path.exists(self.device):
            raise FSResizeError("device does not exist", self.device)

        self.doCheck(intf=intf)

        # The first minimum size can be incorrect if the fs was not
        # properly unmounted. After doCheck the minimum size will be correct
        # so run the check one last time and bump up the size if it was too
        # small.
        self._minInstanceSize = None
        if self.targetSize < self.minSize:
            self.targetSize = self.minSize
            log.info("Minimum size changed, setting targetSize on %s to %s" \
                     % (self.device, self.targetSize))

        w = None
        if intf:
            w = intf.progressWindow(_("Resizing"),
                                    _("Resizing filesystem on %s")
                                    % (self.device,),
                                    100, pulse = True)

        try:
            rc = iutil.execWithPulseProgress(self.resizefsProg,
                                             self.resizeArgs,
                                             stdout="/dev/tty5",
                                             stderr="/dev/tty5",
                                             progress=w)
        except Exception as e:
            raise FSResizeError(e, self.device)
        finally:
            if w:
                w.pop()

        if rc:
            raise FSResizeError("resize failed: %s" % rc, self.device)

        self.doCheck(intf=intf)

        # XXX must be a smarter way to do this
        self._size = self.targetSize
        self.notifyKernel()

    def _getCheckArgs(self):
        argv = []
        argv.extend(self.defaultCheckOptions)
        argv.append(self.device)
        return argv

    def _fsckFailed(self, rc):
        return False

    def _fsckErrorMessage(self, rc):
        return _("Unknown return code: %d.") % (rc,)

    def doCheck(self, intf=None):
        if not self.exists:
            raise FSError("filesystem has not been created")

        if not self.fsckProg:
            return

        if not os.path.exists(self.device):
            raise FSError("device does not exist")

        w = None
        if intf:
            w = intf.progressWindow(_("Checking"),
                                    _("Checking filesystem on %s")
                                    % (self.device),
                                    100, pulse = True)

        try:
            rc = iutil.execWithPulseProgress(self.fsckProg,
                                             self._getCheckArgs(),
                                             stdout="/dev/tty5",
                                             stderr="/dev/tty5",
                                             progress = w)
        except Exception as e:
            raise FSError("filesystem check failed: %s" % e)
        finally:
            if w:
                w.pop()

        if self._fsckFailed(rc):
            hdr = _("%(type)s filesystem check failure on %(device)s: ") % \
                    {"type": self.type, "device": self.device}

            msg = self._fsckErrorMessage(rc)

            if intf:
                help = _("Errors like this usually mean there is a problem "
                         "with the filesystem that will require user "
                         "interaction to repair.  Before restarting "
                         "installation, reboot to rescue mode or another "
                         "system that allows you to repair the filesystem "
                         "interactively.  Restart installation after you "
                         "have corrected the problems on the filesystem.")

                intf.messageWindow(_("Unrecoverable Error"),
                                   hdr + "\n\n" + msg + "\n\n" + help,
                                   custom_icon='error')
                sys.exit(0)
            else:
                raise FSError(hdr + msg)

    def loadModule(self):
        """Load whatever kernel module is required to support this filesystem."""
        global kernel_filesystems

        if not self._modules or self.mountType in kernel_filesystems:
            return

        for module in self._modules:
            try:
                rc = iutil.execWithRedirect("modprobe", [module],
                                            stdout="/dev/tty5",
                                            stderr="/dev/tty5")
            except Exception as e:
                log.error("Could not load kernel module %s: %s" % (module, e))
                self._supported = False
                return

            if rc:
                log.error("Could not load kernel module %s" % module)
                self._supported = False
                return

        # If we successfully loaded a kernel module, for this filesystem, we
        # also need to update the list of supported filesystems.
        kernel_filesystems = get_kernel_filesystems()

    def mount(self, *args, **kwargs):
        """ Mount this filesystem.

            Arguments:

                None

            Keyword Arguments:

                options -- mount options (overrides all other option strings)
                chroot -- prefix to apply to mountpoint
                mountpoint -- mountpoint (overrides self.mountpoint)
        """
        options = kwargs.get("options", "")
        chroot = kwargs.get("chroot", "/")
        mountpoint = kwargs.get("mountpoint")

        if not self.exists:
            raise FSError("filesystem has not been created")

        if not mountpoint:
            mountpoint = self.mountpoint

        if not mountpoint:
            raise FSError("no mountpoint given")

        if self.status:
            return

        if not isinstance(self, NoDevFS) and not os.path.exists(self.device):
            raise FSError("device %s does not exist" % self.device)

        # XXX os.path.join is FUBAR:
        #
        #         os.path.join("/mnt/foo", "/") -> "/"
        #
        #mountpoint = os.path.join(chroot, mountpoint)
        chrootedMountpoint = os.path.normpath("%s/%s" % (chroot, mountpoint))
        iutil.mkdirChain(chrootedMountpoint)
        if flags.selinux:
            ret = isys.resetFileContext(mountpoint, chroot)
            log.info("set SELinux context for mountpoint %s to %s" \
                     % (mountpoint, ret))

        # passed in options override default options
        if not options or not isinstance(options, str):
            options = self.options

        try: 
            rc = isys.mount(self.device, chrootedMountpoint, 
                            fstype=self.mountType,
                            options=options,
                            bindMount=isinstance(self, BindFS))
        except Exception as e:
            raise FSError("mount failed: %s" % e)

        if rc:
            raise FSError("mount failed: %s" % rc)

        if flags.selinux:
            ret = isys.resetFileContext(mountpoint, chroot)
            log.info("set SELinux context for newly mounted filesystem "
                     "root at %s to %s" %(mountpoint, ret))
            isys.setFileContext("%s/lost+found" % mountpoint,
                                lost_and_found_context, chroot)

        self._mountpoint = chrootedMountpoint

    def unmount(self):
        """ Unmount this filesystem. """
        if not self.exists:
            raise FSError("filesystem has not been created")

        if not self._mountpoint:
            # not mounted
            return

        if not os.path.exists(self._mountpoint):
            raise FSError("mountpoint does not exist")

        rc = isys.umount(self._mountpoint, removeDir = False)
        if rc:
            raise FSError("umount failed")

        self._mountpoint = None

    def _getLabelArgs(self, label):
        argv = []
        argv.extend(self.defaultLabelOptions)
        argv.extend([self.device, label])
        return argv 

    def writeLabel(self, label):
        """ Create a label for this filesystem. """
        if not self.exists:
            raise FSError("filesystem has not been created")

        if not self.labelfsProg:
            return

        if not os.path.exists(self.device):
            raise FSError("device does not exist")

        argv = self._getLabelArgs(label)
        rc = iutil.execWithRedirect(self.labelfsProg,
                                    argv,
                                    stderr="/dev/tty5")
        if rc:
            raise FSError("label failed")

        self.label = label
        self.notifyKernel()

    @property
    def isDirty(self):
        return False

    @property
    def mkfsProg(self):
        """ Program used to create filesystems of this type. """
        return self._mkfs

    @property
    def fsckProg(self):
        """ Program used to check filesystems of this type. """
        return self._fsck

    @property
    def resizefsProg(self):
        """ Program used to resize filesystems of this type. """
        return self._resizefs

    @property
    def labelfsProg(self):
        """ Program used to manage labels for this filesystem type. """
        return self._labelfs

    @property
    def migratefsProg(self):
        """ Program used to migrate filesystems of this type. """
        return self._migratefs

    @property
    def infofsProg(self):
        """ Program used to get information for this filesystem type. """
        return self._infofs

    @property
    def migrationTarget(self):
        return self._migrationTarget

    @property
    def utilsAvailable(self):
        # we aren't checking for fsck because we shouldn't need it
        for prog in [self.mkfsProg, self.resizefsProg, self.labelfsProg,
                     self.infofsProg]:
            if not prog:
                continue

            if not filter(lambda d: os.access("%s/%s" % (d, prog), os.X_OK),
                          os.environ["PATH"].split(":")):
                return False

        return True

    @property
    def supported(self):
        log_method_call(self, supported=self._supported)
        return self._supported and self.utilsAvailable

    @property
    def mountable(self):
        return (self.mountType in kernel_filesystems) or \
               (os.access("/sbin/mount.%s" % (self.mountType,), os.X_OK))

    @property
    def defaultFormatOptions(self):
        """ Default options passed to mkfs for this filesystem type. """
        # return a copy to prevent modification
        return self._defaultFormatOptions[:]

    @property
    def defaultMountOptions(self):
        """ Default options passed to mount for this filesystem type. """
        # return a copy to prevent modification
        return self._defaultMountOptions[:]

    @property
    def defaultLabelOptions(self):
        """ Default options passed to labeler for this filesystem type. """
        # return a copy to prevent modification
        return self._defaultLabelOptions[:]

    @property
    def defaultCheckOptions(self):
        """ Default options passed to checker for this filesystem type. """
        # return a copy to prevent modification
        return self._defaultCheckOptions[:]

    def _getOptions(self):
        options = ",".join(self.defaultMountOptions)
        if self.mountopts:
            # XXX should we clobber or append?
            options = self.mountopts
        return options

    def _setOptions(self, options):
        self.mountopts = options

    options = property(_getOptions, _setOptions)

    def _isMigratable(self):
        """ Can filesystems of this type be migrated? """
        return bool(self._migratable and self.migratefsProg and
                    filter(lambda d: os.access("%s/%s"
                                               % (d, self.migratefsProg,),
                                               os.X_OK),
                           os.environ["PATH"].split(":")) and
                    self.migrationTarget)

    migratable = property(_isMigratable)

    def _setMigrate(self, migrate):
        if not migrate:
            self._migrate = migrate
            return

        if self.migratable and self.exists:
            self._migrate = migrate
        else:
            raise ValueError("cannot set migrate on non-migratable filesystem")

    migrate = property(lambda f: f._migrate, lambda f,m: f._setMigrate(m))

    @property
    def type(self):
        _type = self._type
        if self.migrate:
            _type = self.migrationTarget

        return _type

    @property
    def mountType(self):
        if not self._mountType:
            self._mountType = self._type

        return self._mountType

    # These methods just wrap filesystem-specific methods in more
    # generically named methods so filesystems and formatted devices
    # like swap and LVM physical volumes can have a common API.
    def create(self, *args, **kwargs):
        if self.exists:
            raise FSError("filesystem already exists")

        DeviceFormat.create(self, *args, **kwargs)

        return self.doFormat(*args, **kwargs)

    def setup(self, *args, **kwargs):
        """ Mount the filesystem.

            The filesystem will be mounted at the directory indicated by
            self.mountpoint.
        """
        return self.mount(**kwargs)

    def teardown(self, *args, **kwargs):
        return self.unmount(*args, **kwargs)

    @property
    def status(self):
        # FIXME check /proc/mounts or similar
        if not self.exists:
            return False
        return self._mountpoint is not None

    def writeKS(self, f):
        f.write("%s --fstype=%s" % (self.mountpoint, self.type))

        if self.label:
            f.write(" --label=\"%s\"" % self.label)


class Ext2FS(FS):
    """ ext2 filesystem. """
    _type = "ext2"
    _mkfs = "mke2fs"
    _modules = ["ext2"]
    _resizefs = "resize2fs"
    _labelfs = "e2label"
    _fsck = "e2fsck"
    _fsckErrors = {4: _("File system errors left uncorrected."),
                   8: _("Operational error."),
                   16: _("Usage or syntax error."),
                   32: _("e2fsck cancelled by user request."),
                   128: _("Shared library error.")}
    _packages = ["e2fsprogs"]
    _formattable = True
    _supported = True
    _resizable = True
    _bootable = True
    _linuxNative = True
    _maxSize = 8 * 1024 * 1024
    _minSize = 0
    _defaultFormatOptions = []
    _defaultMountOptions = ["defaults"]
    _defaultCheckOptions = ["-f", "-p", "-C", "0"]
    _dump = True
    _check = True
    _migratable = True
    _migrationTarget = "ext3"
    _migratefs = "tune2fs"
    _defaultMigrateOptions = ["-j"]
    _infofs = "dumpe2fs"
    _defaultInfoOptions = ["-h"]
    _existingSizeFields = ["Block count:", "Block size:"]
    _fsProfileSpecifier = "-T"
    partedSystem = fileSystemType["ext2"]

    def _fsckFailed(self, rc):
        for errorCode in self._fsckErrors.keys():
            if rc & errorCode:
                return True
        return False

    def _fsckErrorMessage(self, rc):
        msg = ''

        for errorCode in self._fsckErrors.keys():
            if rc & errorCode:
                msg += "\n" + self._fsckErrors[errorCode]

        return msg.strip()

    def doMigrate(self, intf=None):
        FS.doMigrate(self, intf=intf)
        self.tuneFS()

    def doFormat(self, *args, **kwargs):
        FS.doFormat(self, *args, **kwargs)
        self.tuneFS()

    def tuneFS(self):
        if not isys.ext2HasJournal(self.device):
            # only do this if there's a journal
            return

        try:
            rc = iutil.execWithRedirect("tune2fs",
                                        ["-c0", "-i0",
                                         "-ouser_xattr,acl", self.device],
                                        stdout = "/dev/tty5",
                                        stderr = "/dev/tty5")
        except Exception as e:
            log.error("failed to run tune2fs on %s: %s" % (self.device, e))

    @property
    def minSize(self):
        """ Minimum size for this filesystem in MB. """
        if self._minInstanceSize is None:
            # try once in the beginning to get the minimum size for an
            # existing filesystem.
            size = self._minSize
            blockSize = None

            if self.exists and os.path.exists(self.device):
                # get block size
                buf = iutil.execWithCapture(self.infofsProg,
                                            ["-h", self.device],
                                            stderr="/dev/tty5")
                for line in buf.splitlines():
                    if line.startswith("Block size:"):
                        blockSize = int(line.split(" ")[-1])
                        break

                if blockSize is None:
                    raise FSError("failed to get block size for %s filesystem "
                                  "on %s" % (self.mountType, self.device))

                # get minimum size according to resize2fs
                buf = iutil.execWithCapture(self.resizefsProg,
                                            ["-P", self.device],
                                            stderr="/dev/tty5")
                for line in buf.splitlines():
                    if "minimum size of the filesystem:" not in line:
                        continue

                    # line will look like:
                    # Estimated minimum size of the filesystem: 1148649
                    #
                    # NOTE: The minimum size reported is in blocks.  Convert
                    # to bytes, then megabytes, and finally round up.
                    (text, sep, minSize) = line.partition(": ")
                    size = long(minSize) * blockSize
                    size = math.ceil(size / 1024.0 / 1024.0)
                    break

                if size is None:
                    log.warning("failed to get minimum size for %s filesystem "
                                "on %s" % (self.mountType, self.device))

            self._minInstanceSize = size

        return self._minInstanceSize

    @property
    def isDirty(self):
        return isys.ext2IsDirty(self.device)

    @property
    def resizeArgs(self):
        argv = ["-p", self.device, "%dM" % (self.targetSize,)]
        return argv

register_device_format(Ext2FS)


class Ext3FS(Ext2FS):
    """ ext3 filesystem. """
    _type = "ext3"
    _defaultFormatOptions = ["-t", "ext3"]
    _migrationTarget = "ext4"
    _modules = ["ext3"]
    _defaultMigrateOptions = ["-O", "extents"]
    partedSystem = fileSystemType["ext3"]

    def _isMigratable(self):
        """ Can filesystems of this type be migrated? """
        return (flags.cmdline.has_key("ext4migrate") and
                Ext2FS._isMigratable(self))

    migratable = property(_isMigratable)

register_device_format(Ext3FS)


class Ext4FS(Ext3FS):
    """ ext4 filesystem. """
    _type = "ext4"
    _defaultFormatOptions = ["-t", "ext4"]
    _migratable = False
    _modules = ["ext4"]
    partedSystem = fileSystemType["ext4"]

register_device_format(Ext4FS)


class FATFS(FS):
    """ FAT filesystem. """
    _type = "vfat"
    _mkfs = "mkdosfs"
    _modules = ["vfat"]
    _labelfs = "dosfslabel"
    _fsck = "dosfsck"
    _fsckErrors = {1: _("Recoverable errors have been detected or dosfsck has "
                        "discovered an internal inconsistency."),
                   2: _("Usage error.")}
    _supported = True
    _formattable = True
    _maxSize = 1024 * 1024
    _packages = [ "dosfstools" ]
    _defaultMountOptions = ["umask=0077", "shortname=winnt"]
    # FIXME this should be fat32 in some cases
    partedSystem = fileSystemType["fat16"]

    def _fsckFailed(self, rc):
        if rc >= 1:
            return True
        return False

    def _fsckErrorMessage(self, rc):
        return self._fsckErrors[rc]

register_device_format(FATFS)


class EFIFS(FATFS):
    _type = "efi"
    _mountType = "vfat"
    _modules = ["vfat"]
    _name = "EFI System Partition"
    _minSize = 50
    _maxSize = 256
    _bootable = True

    @property
    def supported(self):
        import platform
        p = platform.getPlatform(None)
        return (isinstance(p, platform.EFI) and
                p.isEfi and
                self.utilsAvailable)

register_device_format(EFIFS)


class BTRFS(FS):
    """ btrfs filesystem """
    _type = "btrfs"
    _mkfs = "mkfs.btrfs"
    _modules = ["btrfs"]
    _resizefs = "btrfsctl"
    _formattable = True
    _linuxNative = True
    _bootable = False
    _maxLabelChars = 256
    _supported = False
    _dump = True
    _check = True
    _packages = ["btrfs-progs"]
    _maxSize = 16 * 1024 * 1024
    # FIXME parted needs to be thaught about btrfs so that we can set the
    # partition table type correctly for btrfs partitions
    # partedSystem = fileSystemType["btrfs"]

    def _getFormatOptions(self, options=None):
        argv = []
        if options and isinstance(options, list):
            argv.extend(options)
        argv.extend(self.defaultFormatOptions)
        if self.label:
            argv.extend(["-L", self.label])
        argv.append(self.device)
        return argv

    @property
    def resizeArgs(self):
        argv = ["-r", "%dm" % (self.targetSize,), self.device]
        return argv

    @property
    def supported(self):
        """ Is this filesystem a supported type? """
        supported = self._supported
        if flags.cmdline.has_key("btrfs"):
            supported = self.utilsAvailable

        return supported

register_device_format(BTRFS)


class GFS2(FS):
    """ gfs2 filesystem. """
    _type = "gfs2"
    _mkfs = "mkfs.gfs2"
    _modules = ["dlm", "gfs2"]
    _formattable = True
    _defaultFormatOptions = ["-j", "1", "-p", "lock_nolock", "-O"]
    _linuxNative = True
    _supported = False
    _dump = True
    _check = True
    _packages = ["gfs2-utils"]
    # FIXME parted needs to be thaught about btrfs so that we can set the
    # partition table type correctly for btrfs partitions
    # partedSystem = fileSystemType["gfs2"]

    @property
    def supported(self):
        """ Is this filesystem a supported type? """
        supported = self._supported
        if flags.cmdline.has_key("gfs2"):
            supported = self.utilsAvailable

        return supported

register_device_format(GFS2)


class JFS(FS):
    """ JFS filesystem """
    _type = "jfs"
    _mkfs = "mkfs.jfs"
    _modules = ["jfs"]
    _labelfs = "jfs_tune"
    _defaultFormatOptions = ["-q"]
    _defaultLabelOptions = ["-L"]
    _maxLabelChars = 16
    _maxSize = 8 * 1024 * 1024
    _formattable = True
    _linuxNative = True
    _supported = False
    _dump = True
    _check = True
    _infofs = "jfs_tune"
    _defaultInfoOptions = ["-l"]
    _existingSizeFields = ["Aggregate block size:", "Aggregate size:"]
    partedSystem = fileSystemType["jfs"]

    @property
    def supported(self):
        """ Is this filesystem a supported type? """
        supported = self._supported
        if flags.cmdline.has_key("jfs"):
            supported = self.utilsAvailable

        return supported

register_device_format(JFS)


class ReiserFS(FS):
    """ reiserfs filesystem """
    _type = "reiserfs"
    _mkfs = "mkreiserfs"
    _resizefs = "resize_reiserfs"
    _labelfs = "reiserfstune"
    _modules = ["reiserfs"]
    _defaultFormatOptions = ["-f", "-f"]
    _defaultLabelOptions = ["-l"]
    _maxLabelChars = 16
    _maxSize = 16 * 1024 * 1024
    _formattable = True
    _linuxNative = True
    _supported = False
    _dump = True
    _check = True
    _packages = ["reiserfs-utils"]
    _infofs = "debugreiserfs"
    _defaultInfoOptions = []
    _existingSizeFields = ["Count of blocks on the device:", "Blocksize:"]
    partedSystem = fileSystemType["reiserfs"]

    @property
    def supported(self):
        """ Is this filesystem a supported type? """
        supported = self._supported
        if flags.cmdline.has_key("reiserfs"):
            supported = self.utilsAvailable

        return supported

    @property
    def resizeArgs(self):
        argv = ["-s", "%dM" % (self.targetSize,), self.device]
        return argv

register_device_format(ReiserFS)


class XFS(FS):
    """ XFS filesystem """
    _type = "xfs"
    _mkfs = "mkfs.xfs"
    _modules = ["xfs"]
    _labelfs = "xfs_admin"
    _defaultFormatOptions = ["-f"]
    _defaultLabelOptions = ["-L"]
    _maxLabelChars = 16
    _maxSize = 16 * 1024 * 1024
    _formattable = True
    _linuxNative = True
    _supported = True
    _dump = True
    _check = True
    _packages = ["xfsprogs"]
    _infofs = "xfs_db"
    _defaultInfoOptions = ["-c", "\"sb 0\"", "-c", "\"p dblocks\"",
                           "-c", "\"p blocksize\""]
    _existingSizeFields = ["dblocks =", "blocksize ="]
    partedSystem = fileSystemType["xfs"]

    def _getLabelArgs(self, label):
        argv = []
        argv.extend(self.defaultLabelOptions)
        argv.extend([label, self.device])
        return argv

register_device_format(XFS)


class HFS(FS):
    _type = "hfs"
    _mkfs = "hformat"
    _modules = ["hfs"]
    _formattable = True
    partedSystem = fileSystemType["hfs"]

register_device_format(HFS)


class AppleBootstrapFS(HFS):
    _type = "appleboot"
    _mountType = "hfs"
    _name = "Apple Bootstrap"
    _bootable = True
    _minSize = 800.00 / 1024.00
    _maxSize = 1

    @property
    def supported(self):
        import platform
        return (isinstance(platform.getPlatform(None), platform.NewWorldPPC)
                and self.utilsAvailable)

    def writeKS(self, f):
        f.write("appleboot --fstype=%s" % self.type)

register_device_format(AppleBootstrapFS)


# this doesn't need to be here
class HFSPlus(FS):
    _type = "hfs+"
    _modules = ["hfsplus"]
    _udevTypes = ["hfsplus"]
    partedSystem = fileSystemType["hfs+"]

register_device_format(HFSPlus)


class NTFS(FS):
    """ ntfs filesystem. """
    _type = "ntfs"
    _resizefs = "ntfsresize"
    _fsck = "ntfsresize"
    _resizable = True
    _minSize = 1
    _maxSize = 16 * 1024 * 1024
    _defaultMountOptions = ["defaults", "ro"]
    _defaultCheckOptions = ["-c"]
    _packages = ["ntfsprogs"]
    _infofs = "ntfsinfo"
    _defaultInfoOptions = ["-m"]
    _existingSizeFields = ["Cluster Size:", "Volume Size in Clusters:"]
    partedSystem = fileSystemType["ntfs"]

    def _fsckFailed(self, rc):
        if rc != 0:
            return True
        return False

    @property
    def minSize(self):
        """ The minimum filesystem size in megabytes. """
        if self._minInstanceSize is None:
            # we try one time to determine the minimum size.
            size = self._minSize
            if self.exists and os.path.exists(self.device):
                minSize = None
                buf = iutil.execWithCapture(self.resizefsProg,
                                            ["-m", self.device],
                                            stderr = "/dev/tty5")
                for l in buf.split("\n"):
                    if not l.startswith("Minsize"):
                        continue
                    try:
                        min = l.split(":")[1].strip()
                        minSize = int(min) + 250
                    except Exception, e:
                        minSize = None
                        log.warning("Unable to parse output for minimum size on %s: %s" %(self.device, e))

                if minSize is None:
                    log.warning("Unable to discover minimum size of filesystem "
                                "on %s" %(self.device,))
                else:
                    size = minSize

            self._minInstanceSize = size

        return self._minInstanceSize

    @property
    def resizeArgs(self):
        # You must supply at least two '-f' options to ntfsresize or
        # the proceed question will be presented to you.
        argv = ["-ff", "-s", "%dM" % (self.targetSize,), self.device]
        return argv


register_device_format(NTFS)


# if this isn't going to be mountable it might as well not be here
class NFS(FS):
    """ NFS filesystem. """
    _type = "nfs"
    _modules = ["nfs"]

    def _deviceCheck(self, devspec):
        if devspec is not None and ":" not in devspec:
            raise ValueError("device must be of the form <host>:<path>")

    @property
    def mountable(self):
        return False

    def _setDevice(self, devspec):
        self._deviceCheck(devspec)
        self._device = devspec

    def _getDevice(self):
        return self._device

    device = property(lambda f: f._getDevice(),
                      lambda f,d: f._setDevice(d),
                      doc="Full path the device this format occupies")
 
register_device_format(NFS)


class NFSv4(NFS):
    """ NFSv4 filesystem. """
    _type = "nfs4"
    _modules = ["nfs4"]

register_device_format(NFSv4)


class Iso9660FS(FS):
    """ ISO9660 filesystem. """
    _type = "iso9660"
    _formattable = False
    _supported = True
    _resizable = False
    _bootable = False
    _linuxNative = False
    _dump = False
    _check = False
    _migratable = False
    _defaultMountOptions = ["ro"]

    def writeKS(self, f):
        return

register_device_format(Iso9660FS)


class NoDevFS(FS):
    """ nodev filesystem base class """
    _type = "nodev"

    def __init__(self, *args, **kwargs):
        FS.__init__(self, *args, **kwargs)
        self.exists = True
        self.device = self.type

    def _setDevice(self, devspec):
        self._device = devspec

    def _getExistingSize(self):
        pass

    def writeKS(self, f):
        return

register_device_format(NoDevFS)


class DevPtsFS(NoDevFS):
    """ devpts filesystem. """
    _type = "devpts"
    _defaultMountOptions = ["gid=5", "mode=620"]

register_device_format(DevPtsFS)


# these don't really need to be here
class ProcFS(NoDevFS):
    _type = "proc"

register_device_format(ProcFS)


class SysFS(NoDevFS):
    _type = "sysfs"

register_device_format(SysFS)


class TmpFS(NoDevFS):
    _type = "tmpfs"

register_device_format(TmpFS)


class BindFS(FS):
    _type = "bind"

    @property
    def mountable(self):
        return True

    def _getExistingSize(self):
        pass

    def writeKS(self, f):
        return

register_device_format(BindFS)


