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
#

""" Filesystem classes for use by anaconda.

    TODO:
        - migration
        - bug 472127: allow creation of tmpfs filesystems (/tmp, /var/tmp, &c)
"""
import os
import isys

from ..errors import *
from . import DeviceFormat, register_device_format
import iutil
from flags import flags

# is this nasty?
log_method_call = iutil.log_method_call

import logging
log = logging.getLogger("storage")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)


fs_configs = {}

def get_kernel_filesystems():
    fs_list = []
    for line in open("/proc/filesystems").readlines():
        fs_list.append(line.split()[-1])
    return fs_list
kernel_filesystems = get_kernel_filesystems()

def fsFromConfig(attrs, *args, **kwargs):
    """ Create an FS instance based on a set of attributes, passing on
        constructor arguments.
    """
    # XXX NOTUSED
    if not attrs.has_key("type"):
        raise ValueError, _("attr dict must include a type")

    fs = FS(*args, **kwargs)
    for (attr, value) in attrs.items():
        setattr(fs, "_%s" % attr, value)

    if attrs["type"] in nodev_filesystems:
        setattr(fs, "_nodev", True)

    return fs

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
    _name = None
    _mkfs = ""                           # mkfs utility
    _resizefs = ""                       # resize utility
    _labelfs = ""                        # labeling utility
    _fsck = ""                           # fs check utility
    _migratefs = ""                      # fs migration utility
    _defaultFormatOptions = []           # default options passed to mkfs
    _defaultMountOptions = ["defaults"]  # default options passed to mount
    _defaultLabelOptions = []
    _defaultCheckOptions = []
    _defaultMigrateOptions = []
    _migrationTarget = None
    lostAndFoundContext = None

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
        # TODO: fsprofiles and other ways to add format args
        self.mountpoint = kwargs.get("mountpoint")
        self.mountopts = kwargs.get("mountopts")
        self.label = kwargs.get("label")
        # filesystem size does not necessarily equal device size
        self._size = kwargs.get("size")
        self._targetSize = self._size
        self._mountpoint = None     # the current mountpoint when mounted

    def _setTargetSize(self, newsize):
        """ Set a target size for this filesystem. """
        if not self.exists:
            raise FSError("filesystem has not been created")

        if newsize is None:
            # unset any outstanding resize request
            self._targetSize = None
            return

        if not self.minSize < newsize < self.maxSize:
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

    @property
    def currentSize(self):
        """ The filesystem's current actual size. """
        size = 0
        if self.exists:
            size = self._size
        return size

    def _getFormatArgs(self, options=None):
        argv = []
        argv.extend(options)
        argv.extend(self.defaultFormatOptions)
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
        log_method_call(self, type=self.type, device=self.device,
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

        argv = self._getFormatArgs(options=options)

        w = None
        if intf:
            w = intf.progressWindow(_("Formatting"),
                                    _("Creating filesystem on %s...")
                                    % (self.device,),
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
                                        stderr = "/dev/tty5",
                                        searchPath = 1)
        except Exception as e:
            raise FSMigrateError("filesystem migration failed: %s" % e,
                                 self.device)

        if rc:
            raise FSMigrateError("filesystem migration failed: %s" % rc,
                                 self.device)

        # the other option is to actually replace this instance with an
        # instance of the new filesystem type.
        self._type = self.migrationTarget

    def _getResizeArgs(self):
        argv = [self.device, self.targetSize]
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
            # should this instead raise an exception?
            return

        if self.targetSize == self.currentSize:
            return

        if not self.resizefsProg:
            return

        if not os.path.exists(self.device):
            raise FSResizeError("device does not exist", self.device)

        self.doCheck(intf=intf)

        argv = self._getResizeArgs()

        w = None
        if intf:
            w = intf.progressWindow(_("Resizing"),
                                    _("Resizing filesystem on %s...")
                                    % (self.device,),
                                    100, pulse = True)

        try:
            rc = iutil.execWithPulseProgress(self.resizefsProg,
                                             argv,
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

        # XXX must be a smarter way to do this
        self._size = self.targetSize
        self.notifyKernel()

    def _getCheckArgs(self):
        argv = []
        argv.extend(self.defaultCheckOptions)
        argv.append(self.device)

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
                                    _("Checking filesystem on %s...")
                                    % (self.device),
                                    100, pulse = True)

        try:
            rc = iutil.execWithPulseProgress(self.fsckProg,
                                             argv,
                                             stdout="/dev/tty5",
                                             stderr="/dev/tty5",
                                             progress = w)
        except Exception as e:
            raise FSError("filesystem check failed: %s" % e)
        finally:
            if w:
                w.pop()

        if rc >= 4:
            raise FSError("filesystem check failed: %s" % rc)

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
            raise FSError("filesystem is already mounted")

        if not isinstance(self, NoDevFS) and not os.path.exists(self.device):
            raise FSError("device %s does not exist" % self.device)

        # XXX os.path.join is FUBAR:
        #
        #         os.path.join("/mnt/foo", "/") -> "/"
        #
        #mountpoint = os.path.join(chroot, mountpoint)
        mountpoint = os.path.normpath("%s/%s" % (chroot, mountpoint))
        iutil.mkdirChain(mountpoint)
        if flags.selinux:
            ret = isys.resetFileContext(mountpoint)
            log.info("set SELinux context for mountpoint %s to %s" \
                     % (mountpoint, ret))

        # passed in options override default options
        if not options or not isinstance(options, str):
            options = self.options
       
        try: 
            rc = isys.mount(self.device, mountpoint, 
                            fstype=self.type,
                            options=options,
                            bindMount=isinstance(self, BindFS))
        except Exception as e:
            raise FSError("mount failed: %s" % e)

        if rc:
            raise FSError("mount failed: %s" % rc)

        if flags.selinux:
            ret = isys.resetFileContext(mountpoint)
            log.info("set SELinux context for newly mounted filesystem "
                     "root at %s to %s" %(mountpoint, ret))
            if self.lostAndFoundContext is None:
                self.lostAndFoundContext = isys.matchPathContext("/lost+found")
            isys.setFileContext("%s/lost+found" % mountpoint,
                                self.lostAndFoundContext)

        self._mountpoint = mountpoint

    def unmount(self):
        """ Unmount this filesystem. """
        if not self.exists:
            raise FSError("filesystem has not been created")

        if not self._mountpoint:
            # not mounted
            return

        if not os.path.exists(self._mountpoint):
            raise FSError("mountpoint does not exist")

        rc = isys.umount(self._mountpoint)
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
                                    stderr="/dev/tty5",
                                    searchPath=1)
        if rc:
            raise FSError("label failed")

        self.fslabel = label
        self.notifyKernel()

    @property
    def isDirty(self):
        return False

    @property
    def mkfsProg(self):
        """ Program used to create filesystems of this type. """
        return self._mkfs

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
    def migrationTarget(self):
        return self._migrationTarget

    def supported(self):
        # we aren't checking for fsck because we shouldn't need it
        for prog in [self.mkfsProg, self.resizefsProg, self.labelfsProg]:
            if not prog:
                continue

            if not filter(lambda d: os.access("%s/%s" % (d, prog), os.X_OK),
                          os.environ["PATH"].split(":")):
                return False

        return True

    @property
    def mountable(self):
        return self.type in kernel_filesystems

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

    @property
    def migratable(self):
        """ Can filesystems of this type be migrated? """
        return (self._migratable and self.migratefsProg and
                filter(lambda d: os.access("%s/%s" % (d, self.migratefsProg),
                                           os.X_OK),
                       os.environ["PATH"].split(":")) and
                self.migrationTarget)

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

    """ These methods just wrap filesystem-specific methods in more
        generically named methods so filesystems and formatted devices
        like swap and LVM physical volumes can have a common API.
    """
    def create(self, *args, **kwargs):
        if self.exists:
            raise FSError("filesystem already exists")

        DeviceFormat.create(self, *args, **kwargs)

        return self.doFormat(*args, **kwargs)

    def setup(self, *args, **kwargs):
        """ Mount the filesystem.

            THe filesystem will be mounted at the directory indicated by
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


class Ext2FS(FS):
    """ ext2 filesystem. """
    _type = "ext2"
    _mkfs = "mke2fs"
    _resizefs = "resize2fs"
    _labelfs = "e2label"
    _fsck = "e2fsck"
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

    @property
    def minSize(self):
        """ Minimum size for this filesystem in MB. """
        size = self._minSize
        if self.exists:
            if not os.path.exists(self.device):
                raise FSError("device does not exist")

            buf = iutil.execWithCapture(self.resizefsProg,
                                        ["-P", self.device],
                                        stderr="/dev/tty5")
            size = None
            for line in buf.splitlines():
                if "minimum size of the filesystem:" not in line:
                    continue

                (text, sep, minSize) = line.partition(": ")

                size = int(minSize) / 1024.0

            if size is None:
                raise FSError("failed to get minimum fs size")

        return size

    @property
    def isDirty(self):
        return isys.ext2IsDirty(self.device)

register_device_format(Ext2FS)


class Ext3FS(Ext2FS):
    """ ext3 filesystem. """
    _type = "ext3"
    _defaultFormatOptions = ["-t", "ext3"]
    _migrationTarget = "ext4"
    _defaultMigrateOptions = ["-O", "extents"]

register_device_format(Ext3FS)


class Ext4FS(Ext3FS):
    """ ext4 filesystem. """
    _type = "ext4"
    _bootable = False
    _defaultFormatOptions = ["-t", "ext4"]
    _migratable = False

register_device_format(Ext4FS)


class FATFS(FS):
    """ FAT filesystem.

        XXX Do we want to subclass this for EFI or twiddle bootable based
            on the platform?
    """
    _type = "vfat"
    _mkfs = "mkdosfs"
    _labelfs = "dosfslabel"
    _fsck = "dosfsck"
    _formattable = True
    _maxSize = 1024 * 1024
    _packages = [ "dosfstools" ]
    _defaultMountOptions = ["umask=0077", "shortname=winnt"]

    @property
    def bootable(self):
        retval = self._bootable
        #if self.type in platform.bootableFSTypes:
        #    retval = True

        return retval

register_device_format(FATFS)


class BTRFS(FS):
    """ btrfs filesystem """
    _type = "btrfs"
    _mkfs = "mkfs.btrfs"
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

    def _getFormatArgs(self, options=None):
        argv = []
        argv.extend(options)
        argv.extend(self.defaultFormatArgs)
        if self.fslabel:
            argv.extend(["-L", self.fslabel])
        argv.append(self.device)
        return argv

    def _getResizeArgs(self):
        argv = ["-r", self.targetSize, self.device]
        return argv

register_device_format(BTRFS)


class GFS2(FS):
    """ gfs2 filesystem. """
    _type = "gfs2"
    _mkfs = "mkfs.gfs2"
    _formattable = True
    _defaultFormatOptions = ["-j", "1", "-p", "lock_nolock", "-O"]
    _linuxNative = True
    _supported = False
    _dump = True
    _check = True
    _packages = ["gfs2-utils"]

    @property
    def supported(self):
        """ Is this filesystem a supported type? """
        supported = self._supported
        if flags.cmdline.has_key("gfs2"):
            supported = True

        return supported

register_device_format(GFS2)


class JFS(FS):
    """ JFS filesystem """
    _type = "jfs"
    _mkfs = "mkfs.jfs"
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

register_device_format(JFS)


class XFS(FS):
    """ XFS filesystem """
    _type = "xfs"
    _mkfs = "mkfs.xfs"
    _labelfs = "xfs_admin"
    _defaultFormatOptions = ["-f"]
    _defaultLabelOptions = ["-L"]
    _maxLabelChars = 16
    _maxSize = 16 * 1024 * 1024
    _formattable = True
    _linuxNative = True
    _supported = False
    _dump = True
    _check = True
    _packages = ["xfsprogs"]

register_device_format(XFS)


class HFS(FS):
    _type = "hfs"
    _mkfs = "hformat"
    _formattable = True

register_device_format(HFS)


# this doesn't need to be here
class HFSPlus(FS):
    _type = "hfs+"
    _udevTypes = ["hfsplus"]

register_device_format(HFSPlus)


class NTFS(FS):
    """ ntfs filesystem. """
    _type = "ntfs"
    _resizefs = "ntfsresize"
    _resizable = True
    _minSize = 1
    _defaultMountOptions = "defaults"
    #_packages = ["ntfsprogs"]

    def minSize(self):
        """ The minimum filesystem size in megabytes. """
        size = self._minSize
        if self.exists:
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

        return size

register_device_format(NTFS)


# if this isn't going to be mountable it might as well not be here
class NFS(FS):
    """ NFS filesystem. """
    _type = "nfs"

    def _deviceCheck(self, devspec):
        if not ":" in devspec:
            raise ValueError("device must be of the form <host>:<path>")

    @property
    def mountable(self):
        return False
 
register_device_format(NFS)


class NFSv4(NFS):
    """ NFSv4 filesystem. """
    _type = "nfs4"

register_device_format(NFSv4)

class NoDevFS(FS):
    """ nodev filesystem base class """
    _type = "nodev"

    def __init__(self, *args, **kwargs):
        FS.__init__(self, *args, **kwargs)

    def _deviceCheck(self, devspec):
        pass

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

register_device_format(BindFS)


