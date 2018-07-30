#
# Copyright (C) 2009-2017  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

"""This module provides storage functions related to OS installation."""

import shlex
import os
import stat
import time
import parted
import shutil

import gi
gi.require_version("BlockDev", "2.0")

from gi.repository import BlockDev as blockdev

from pykickstart.constants import AUTOPART_TYPE_LVM, NVDIMM_ACTION_USE, NVDIMM_ACTION_RECONFIGURE

from blivet import arch, udev
from blivet import util as blivet_util
from blivet.blivet import Blivet
from blivet.storage_log import log_exception_info
from blivet.devices import FileDevice, NFSDevice, NoDevice, OpticalDevice, NetworkStorageDevice, \
    DirectoryDevice, MDRaidArrayDevice, PartitionDevice, BTRFSSubVolumeDevice, TmpFSDevice, \
    LVMLogicalVolumeDevice, LVMVolumeGroupDevice, BTRFSDevice
from blivet.errors import FSTabTypeMismatchError, UnrecognizedFSTabEntryError, StorageError, FSResizeError, FormatResizeError, UnknownSourceDeviceError
from blivet.formats import get_device_format_class
from blivet.formats import get_format
from blivet.flags import flags as blivet_flags
from blivet.iscsi import iscsi
from blivet.fcoe import fcoe
from blivet.static_data import nvdimm
from blivet.size import Size
from blivet.devicelibs.crypto import DEFAULT_LUKS_VERSION

from pyanaconda.core import util
from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.bootloader import get_bootloader
from pyanaconda.core.constants import shortProductName, CLEAR_PARTITIONS_NONE, \
    CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_ALL, CLEAR_PARTITIONS_LIST, CLEAR_PARTITIONS_DEFAULT
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.platform import EFI
from pyanaconda.platform import platform as _platform
from pyanaconda.modules.common.constants.services import NETWORK, STORAGE
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, DISK_INITIALIZATION, \
    AUTO_PARTITIONING, ZFCP

import logging
log = logging.getLogger("anaconda.storage")


def enable_installer_mode():
    """ Configure the module for use by anaconda (OS installer). """
    blivet_util.program_log_lock = program_log_lock

    # always enable the debug mode when in the installer mode so that we
    # have more data in the logs for rare cases that are hard to reproduce
    blivet_flags.debug = True

    # We don't want image installs writing backups of the *image* metadata
    # into the *host's* /etc/lvm. This can get real messy on build systems.
    if blivet_flags.image_install:
        blivet_flags.lvm_metadata_backup = False

    blivet_flags.auto_dev_updates = True
    blivet_flags.selinux_reset_fcon = True
    blivet_flags.keep_empty_ext_partitions = False
    blivet_flags.discard_new = True

    udev.device_name_blacklist = [r'^mtd', r'^mmcblk.+boot', r'^mmcblk.+rpmb', r'^zram', '^ndblk']


def copy_to_system(source):
    if not os.access(source, os.R_OK):
        log.info("copy_to_system: source '%s' does not exist.", source)
        return False

    target = util.getSysroot() + source
    target_dir = os.path.dirname(target)
    log.debug("copy_to_system: '%s' -> '%s'.", source, target)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    shutil.copy(source, target)
    return True


def update_blivet_flags(blivet_flags, anaconda_flags):  # pylint: disable=redefined-outer-name
    """
    Set installer-specific flags. This changes blivet default flags by
    either flipping the original value, or it assigns the flag value
    based on anaconda settings that are passed in.

    :param blivet_flags: Blivet flags
    :type flags: :class:`blivet.flags.Flags`
    :param anaconda_flags: anaconda flags
    :type anaconda_flags: :class:`pyanaconda.flags.Flags`
    """
    blivet_flags.testing = anaconda_flags.testing
    blivet_flags.automated_install = anaconda_flags.automatedInstall
    blivet_flags.live_install = anaconda_flags.livecdInstall
    blivet_flags.image_install = anaconda_flags.imageInstall

    blivet_flags.selinux = anaconda_flags.selinux

    blivet_flags.arm_platform = anaconda_flags.armPlatform
    blivet_flags.gpt = anaconda_flags.gpt

    blivet_flags.multipath_friendly_names = anaconda_flags.mpathFriendlyNames
    blivet_flags.allow_imperfect_devices = anaconda_flags.rescue_mode

    blivet_flags.ibft = anaconda_flags.ibft
    blivet_flags.dmraid = anaconda_flags.dmraid


def release_from_redhat_release(fn):
    """
    Attempt to identify the installation of a Linux distribution via
    /etc/redhat-release.  This file must already have been verified to exist
    and be readable.

    :param fn: an open filehandle on /etc/redhat-release
    :type fn: filehandle
    :returns: The distribution's name and version, or None for either or both
    if they cannot be determined
    :rtype: (string, string)
    """
    rel_name = None
    rel_ver = None

    with open(fn) as f:
        try:
            relstr = f.readline().strip()
        except (IOError, AttributeError):
            relstr = ""

    # get the release name and version
    # assumes that form is something
    # like "Red Hat Linux release 6.2 (Zoot)"
    (product, sep, version) = relstr.partition(" release ")
    if sep:
        rel_name = product
        rel_ver = version.split()[0]

    return (rel_name, rel_ver)


def release_from_os_release(fn):
    """
    Attempt to identify the installation of a Linux distribution via
    /etc/os-release.  This file must already have been verified to exist
    and be readable.

    :param fn: an open filehandle on /etc/os-release
    :type fn: filehandle
    :returns: The distribution's name and version, or None for either or both
    if they cannot be determined
    :rtype: (string, string)
    """
    rel_name = None
    rel_ver = None

    with open(fn, "r") as f:
        parser = shlex.shlex(f)

        while True:
            key = parser.get_token()
            if key == parser.eof:
                break
            elif key == "NAME":
                # Throw away the "=".
                parser.get_token()
                rel_name = parser.get_token().strip("'\"")
            elif key == "VERSION_ID":
                # Throw away the "=".
                parser.get_token()
                rel_ver = parser.get_token().strip("'\"")

    return (rel_name, rel_ver)


def get_release_string():
    """
    Attempt to identify the installation of a Linux distribution by checking
    a previously mounted filesystem for several files.  The filesystem must
    be mounted under the target physical root.

    :returns: The machine's arch, distribution name, and distribution version
    or None for any parts that cannot be determined
    :rtype: (string, string, string)
    """
    rel_name = None
    rel_ver = None
    sysroot = util.getSysroot()

    try:
        rel_arch = blivet_util.capture_output(["arch"], root=sysroot).strip()
    except OSError:
        rel_arch = None

    filename = "%s/etc/redhat-release" % sysroot
    if os.access(filename, os.R_OK):
        (rel_name, rel_ver) = release_from_redhat_release(filename)
    else:
        filename = "%s/etc/os-release" % sysroot
        if os.access(filename, os.R_OK):
            (rel_name, rel_ver) = release_from_os_release(filename)

    return (rel_arch, rel_name, rel_ver)


def parse_fstab(devicetree, chroot=None):
    """ parse /etc/fstab and return a tuple of a mount dict and swap list """
    if not chroot or not os.path.isdir(chroot):
        chroot = util.getSysroot()

    mounts = {}
    swaps = []
    path = "%s/etc/fstab" % chroot
    if not os.access(path, os.R_OK):
        # XXX should we raise an exception instead?
        log.info("cannot open %s for read", path)
        return (mounts, swaps)

    blkid_tab = BlkidTab(chroot=chroot)
    try:
        blkid_tab.parse()
        log.debug("blkid.tab devs: %s", list(blkid_tab.devices.keys()))
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "error parsing blkid.tab")
        blkid_tab = None

    crypt_tab = CryptTab(devicetree, blkid_tab=blkid_tab, chroot=chroot)
    try:
        crypt_tab.parse(chroot=chroot)
        log.debug("crypttab maps: %s", list(crypt_tab.mappings.keys()))
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "error parsing crypttab")
        crypt_tab = None

    with open(path) as f:
        log.debug("parsing %s", path)
        for line in f.readlines():

            (line, _pound, _comment) = line.partition("#")
            fields = line.split(None, 4)

            if len(fields) < 5:
                continue

            (devspec, mountpoint, fstype, options, _rest) = fields

            # find device in the tree
            device = devicetree.resolve_device(devspec,
                                               crypt_tab=crypt_tab,
                                               blkid_tab=blkid_tab,
                                               options=options)

            if device is None:
                continue

            if fstype != "swap":
                mounts[mountpoint] = device
            else:
                swaps.append(device)

    return (mounts, swaps)


def find_existing_installations(devicetree, teardown_all=True):
    """Find existing GNU/Linux installations on devices from the devicetree.
    :param devicetree: devicetree to find existing installations in
    :type devicetree: :class:`blivet.devicetree.DeviceTree`
    :param bool teardown_all: whether to tear down all devices in the
                              devicetree in the end
    :return: roots of all found installations
    :rtype: list of :class:`Root`

    """
    try:
        roots = _find_existing_installations(devicetree)
        return roots
    except Exception:  # pylint: disable=broad-except
        log_exception_info(log.info, "failure detecting existing installations")
    finally:
        if teardown_all:
            devicetree.teardown_all()

    return []


def _find_existing_installations(devicetree):
    if not os.path.exists(util.getTargetPhysicalRoot()):
        blivet_util.makedirs(util.getTargetPhysicalRoot())

    sysroot = util.getSysroot()
    roots = []
    direct_devices = (dev for dev in devicetree.devices if dev.direct)
    for device in direct_devices:
        if not device.format.linux_native or not device.format.mountable or \
           not device.controllable:
            continue

        try:
            device.setup()
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.warning, "setup of %s failed", [device.name])
            continue

        options = device.format.options + ",ro"
        try:
            device.format.mount(options=options, mountpoint=sysroot)
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.warning, "mount of %s as %s failed", [device.name, device.format.type])
            blivet_util.umount(mountpoint=sysroot)
            continue

        if not os.access(sysroot + "/etc/fstab", os.R_OK):
            blivet_util.umount(mountpoint=sysroot)
            device.teardown()
            continue

        try:
            (architecture, product, version) = get_release_string()
        except ValueError:
            name = _("Linux on %s") % device.name
        else:
            # I'd like to make this finer grained, but it'd be very difficult
            # to translate.
            if not product or not version or not architecture:
                name = _("Unknown Linux")
            elif "linux" in product.lower():
                name = _("%(product)s %(version)s for %(arch)s") % \
                    {"product": product, "version": version, "arch": architecture}
            else:
                name = _("%(product)s Linux %(version)s for %(arch)s") % \
                    {"product": product, "version": version, "arch": architecture}

        (mounts, swaps) = parse_fstab(devicetree, chroot=sysroot)
        blivet_util.umount(mountpoint=sysroot)
        if not mounts and not swaps:
            # empty /etc/fstab. weird, but I've seen it happen.
            continue
        roots.append(Root(mounts=mounts, swaps=swaps, name=name))

    return roots


class StorageDiscoveryConfig(object):

    """ Class to encapsulate various detection/initialization parameters. """

    def __init__(self):

        # storage configuration variables
        self.ignore_disk_interactive = False
        self.clear_part_type = CLEAR_PARTITIONS_DEFAULT
        self.clear_part_disks = []
        self.clear_part_devices = []
        self.initialize_disks = False
        self.protected_dev_specs = []
        self.zero_mbr = False

        # Whether clear_partitions removes scheduled/non-existent devices and
        # disklabels depends on this flag.
        self.clear_non_existent = False

    def update(self, *args, **kwargs):
        """Update configuration."""
        disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)

        self.clear_part_type = disk_init_proxy.InitializationMode
        self.clear_part_disks = disk_init_proxy.DrivesToClear
        self.clear_part_devices = disk_init_proxy.DevicesToClear
        self.initialize_disks = disk_init_proxy.InitializeLabelsEnabled
        self.zero_mbr = disk_init_proxy.FormatUnrecognizedEnabled


class FSSet(object):

    """ A class to represent a set of filesystems. """

    def __init__(self, devicetree):
        self.devicetree = devicetree
        self.crypt_tab = None
        self.blkid_tab = None
        self.orig_fstab = None
        self.active = False
        self._dev = None
        self._devpts = None
        self._sysfs = None
        self._proc = None
        self._devshm = None
        self._usb = None
        self._selinux = None
        self._run = None
        self._efivars = None
        self._fstab_swaps = set()
        self.preserve_lines = []     # lines we just ignore and preserve

    @property
    def sysfs(self):
        if not self._sysfs:
            self._sysfs = NoDevice(fmt=get_format("sysfs", device="sysfs", mountpoint="/sys"))
        return self._sysfs

    @property
    def dev(self):
        if not self._dev:
            self._dev = DirectoryDevice("/dev",
                                        fmt=get_format("bind", device="/dev", mountpoint="/dev", exists=True),
                                        exists=True)

        return self._dev

    @property
    def devpts(self):
        if not self._devpts:
            self._devpts = NoDevice(fmt=get_format("devpts", device="devpts", mountpoint="/dev/pts"))
        return self._devpts

    @property
    def proc(self):
        if not self._proc:
            self._proc = NoDevice(fmt=get_format("proc", device="proc", mountpoint="/proc"))
        return self._proc

    @property
    def devshm(self):
        if not self._devshm:
            self._devshm = NoDevice(fmt=get_format("tmpfs", device="tmpfs", mountpoint="/dev/shm"))
        return self._devshm

    @property
    def usb(self):
        if not self._usb:
            self._usb = NoDevice(fmt=get_format("usbfs", device="usbfs", mountpoint="/proc/bus/usb"))
        return self._usb

    @property
    def selinux(self):
        if not self._selinux:
            self._selinux = NoDevice(fmt=get_format("selinuxfs", device="selinuxfs", mountpoint="/sys/fs/selinux"))
        return self._selinux

    @property
    def efivars(self):
        if not self._efivars:
            self._efivars = NoDevice(fmt=get_format("efivarfs", device="efivarfs", mountpoint="/sys/firmware/efi/efivars"))
        return self._efivars

    @property
    def run(self):
        if not self._run:
            self._run = DirectoryDevice("/run",
                                        fmt=get_format("bind", device="/run", mountpoint="/run", exists=True),
                                        exists=True)

        return self._run

    @property
    def devices(self):
        return sorted(self.devicetree.devices, key=lambda d: d.path)

    @property
    def mountpoints(self):
        return self.devicetree.mountpoints

    def _parse_one_line(self, devspec, mountpoint, fstype, options, _dump="0", _passno="0"):
        """Parse an fstab entry for a device, return the corresponding device.

           The parameters correspond to the items in a single entry in the
           order in which they occur in the entry.

           :returns: the device corresponding to the entry
           :rtype: :class:`blivet.devices.Device`
        """

        # no sense in doing any legwork for a noauto entry
        if "noauto" in options.split(","):
            log.info("ignoring noauto entry")
            raise UnrecognizedFSTabEntryError()

        # find device in the tree
        device = self.devicetree.resolve_device(devspec,
                                                crypt_tab=self.crypt_tab,
                                                blkid_tab=self.blkid_tab,
                                                options=options)

        if device:
            # fall through to the bottom of this block
            pass
        elif devspec.startswith("/dev/loop"):
            # FIXME: create devices.LoopDevice
            log.warning("completely ignoring your loop mount")
        elif ":" in devspec and fstype.startswith("nfs"):
            # NFS -- preserve but otherwise ignore
            device = NFSDevice(devspec,
                               fmt=get_format(fstype,
                                              exists=True,
                                              device=devspec))
        elif devspec.startswith("/") and fstype == "swap":
            # swap file
            device = FileDevice(devspec,
                                parents=get_containing_device(devspec, self.devicetree),
                                fmt=get_format(fstype,
                                               device=devspec,
                                               exists=True),
                                exists=True)
        elif fstype == "bind" or "bind" in options:
            # bind mount... set fstype so later comparison won't
            # turn up false positives
            fstype = "bind"

            # This is probably not going to do anything useful, so we'll
            # make sure to try again from FSSet.mount_filesystems. The bind
            # mount targets should be accessible by the time we try to do
            # the bind mount from there.
            parents = get_containing_device(devspec, self.devicetree)
            device = DirectoryDevice(devspec, parents=parents, exists=True)
            device.format = get_format("bind",
                                       device=device.path,
                                       exists=True)
        elif mountpoint in ("/proc", "/sys", "/dev/shm", "/dev/pts",
                            "/sys/fs/selinux", "/proc/bus/usb", "/sys/firmware/efi/efivars"):
            # drop these now -- we'll recreate later
            return None
        else:
            # nodev filesystem -- preserve or drop completely?
            fmt = get_format(fstype)
            fmt_class = get_device_format_class("nodev")
            if devspec == "none" or \
               (fmt_class and isinstance(fmt, fmt_class)):
                device = NoDevice(fmt=fmt)

        if device is None:
            log.error("failed to resolve %s (%s) from fstab", devspec,
                      fstype)
            raise UnrecognizedFSTabEntryError()

        device.setup()
        fmt = get_format(fstype, device=device.path, exists=True)
        if fstype != "auto" and None in (device.format.type, fmt.type):
            log.info("Unrecognized filesystem type for %s (%s)",
                     device.name, fstype)
            device.teardown()
            raise UnrecognizedFSTabEntryError()

        # make sure, if we're using a device from the tree, that
        # the device's format we found matches what's in the fstab
        ftype = getattr(fmt, "mount_type", fmt.type)
        dtype = getattr(device.format, "mount_type", device.format.type)
        if hasattr(fmt, "test_mount") and fstype != "auto" and ftype != dtype:
            log.info("fstab says %s at %s is %s", dtype, mountpoint, ftype)
            if fmt.test_mount():     # pylint: disable=no-member
                device.format = fmt
            else:
                device.teardown()
                raise FSTabTypeMismatchError("%s: detected as %s, fstab says %s"
                                             % (mountpoint, dtype, ftype))
        del ftype
        del dtype

        if hasattr(device.format, "mountpoint"):
            device.format.mountpoint = mountpoint

        device.format.options = options

        return device

    def parse_fstab(self, chroot=None):
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
            chroot = util.getSysroot()

        path = "%s/etc/fstab" % chroot
        if not os.access(path, os.R_OK):
            # XXX should we raise an exception instead?
            log.info("cannot open %s for read", path)
            return

        blkid_tab = BlkidTab(chroot=chroot)
        try:
            blkid_tab.parse()
            log.debug("blkid.tab devs: %s", list(blkid_tab.devices.keys()))
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.info, "error parsing blkid.tab")
            blkid_tab = None

        crypt_tab = CryptTab(self.devicetree, blkid_tab=blkid_tab, chroot=chroot)
        try:
            crypt_tab.parse(chroot=chroot)
            log.debug("crypttab maps: %s", list(crypt_tab.mappings.keys()))
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.info, "error parsing crypttab")
            crypt_tab = None

        self.blkid_tab = blkid_tab
        self.crypt_tab = crypt_tab

        with open(path) as f:
            log.debug("parsing %s", path)

            lines = f.readlines()

            # save the original file
            self.orig_fstab = ''.join(lines)

            for line in lines:

                (line, _pound, _comment) = line.partition("#")
                fields = line.split()

                if not 4 <= len(fields) <= 6:
                    continue

                try:
                    device = self._parse_one_line(*fields)
                except UnrecognizedFSTabEntryError:
                    # just write the line back out as-is after upgrade
                    self.preserve_lines.append(line)
                    continue

                if not device:
                    continue

                if device not in self.devicetree.devices:
                    try:
                        self.devicetree._add_device(device)
                    except ValueError:
                        # just write duplicates back out post-install
                        self.preserve_lines.append(line)

    def turn_on_swap(self, root_path=""):
        """ Activate the system's swap space. """
        for device in self.swap_devices:
            if isinstance(device, FileDevice):
                # set up FileDevices' parents now that they are accessible
                target_dir = "%s/%s" % (root_path, device.path)
                parent = get_containing_device(target_dir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s", device.path)
                    device.parents = []
                    self.devicetree._remove_device(device)
                    continue
                else:
                    device.parents = [parent]

            while True:
                try:
                    device.setup()
                    device.format.setup()
                except (StorageError, blockdev.BlockDevError) as e:
                    if error_handler.cb(e) == ERROR_RAISE:
                        raise
                else:
                    break

    def mount_filesystems(self, root_path="", read_only=None, skip_root=False):
        """ Mount the system's filesystems.

            :param str root_path: the root directory for this filesystem
            :param read_only: read only option str for this filesystem
            :type read_only: str or None
            :param bool skip_root: whether to skip mounting the root filesystem
        """
        devices = list(self.mountpoints.values()) + self.swap_devices
        devices.extend([self.dev, self.devshm, self.devpts, self.sysfs,
                        self.proc, self.selinux, self.usb, self.run])
        if isinstance(_platform, EFI):
            devices.append(self.efivars)
        devices.sort(key=lambda d: getattr(d.format, "mountpoint", ""))

        for device in devices:
            if not device.format.mountable or not device.format.mountpoint:
                continue

            if skip_root and device.format.mountpoint == "/":
                continue

            options = device.format.options
            if "noauto" in options.split(","):
                continue

            if device.format.type == "bind" and device not in [self.dev, self.run]:
                # set up the DirectoryDevice's parents now that they are
                # accessible
                #
                # -- bind formats' device and mountpoint are always both
                #    under the chroot. no exceptions. none, damn it.
                target_dir = "%s/%s" % (root_path, device.path)
                parent = get_containing_device(target_dir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s", device.path)
                    device.parents = []
                    self.devicetree._remove_device(device)
                    continue
                else:
                    device.parents = [parent]

            try:
                device.setup()
            except Exception as e:  # pylint: disable=broad-except
                log_exception_info(fmt_str="unable to set up device %s", fmt_args=[device])
                if error_handler.cb(e) == ERROR_RAISE:
                    raise
                else:
                    continue

            if read_only:
                options = "%s,%s" % (options, read_only)

            try:
                device.format.setup(options=options,
                                    chroot=root_path)
            except Exception as e:  # pylint: disable=broad-except
                log_exception_info(log.error, "error mounting %s on %s", [device.path, device.format.mountpoint])
                if error_handler.cb(e) == ERROR_RAISE:
                    raise

        self.active = True

    def umount_filesystems(self, swapoff=True):
        """ unmount filesystems, except swap if swapoff == False """
        devices = list(self.mountpoints.values()) + self.swap_devices
        devices.extend([self.dev, self.devshm, self.devpts, self.sysfs,
                        self.proc, self.usb, self.selinux, self.run])
        if isinstance(_platform, EFI):
            devices.append(self.efivars)
        devices.sort(key=lambda d: getattr(d.format, "mountpoint", ""))
        devices.reverse()
        for device in devices:
            if (not device.format.mountable) or \
               (device.format.type == "swap" and not swapoff):
                continue

            # Unmount the devices
            device.format.teardown()

        self.active = False

    def create_swap_file(self, device, size):
        """ Create and activate a swap file under storage root. """
        filename = "/SWAP"
        count = 0
        basedir = os.path.normpath("%s/%s" % (util.getTargetPhysicalRoot(),
                                              device.format.mountpoint))
        while os.path.exists("%s/%s" % (basedir, filename)) or \
                self.devicetree.get_device_by_name(filename):
            count += 1
            filename = "/SWAP-%d" % count

        dev = FileDevice(filename,
                         size=size,
                         parents=[device],
                         fmt=get_format("swap", device=filename))
        dev.create()
        dev.setup()
        dev.format.create()
        dev.format.setup()
        # nasty, nasty
        self.devicetree._add_device(dev)

    def mk_dev_root(self):
        root = self.root_device
        sysroot = util.getSysroot()
        dev = "%s/%s" % (sysroot, root.path)
        if not os.path.exists("%s/dev/root" % (sysroot,)) and os.path.exists(dev):
            rdev = os.stat(dev).st_rdev
            os.mknod("%s/dev/root" % (sysroot,), stat.S_IFBLK | 0o600, rdev)

    @property
    def swap_devices(self):
        swaps = []
        for device in self.devices:
            if device.format.type == "swap":
                swaps.append(device)
        return swaps

    @property
    def root_device(self):
        for path in ["/", util.getTargetPhysicalRoot()]:
            for device in self.devices:
                try:
                    mountpoint = device.format.mountpoint
                except AttributeError:
                    mountpoint = None

                if mountpoint == path:
                    return device

    def write(self):
        """ write out all config files based on the set of filesystems """
        sysroot = util.getSysroot()
        # /etc/fstab
        fstab_path = os.path.normpath("%s/etc/fstab" % sysroot)
        fstab = self.fstab()
        open(fstab_path, "w").write(fstab)

        # /etc/crypttab
        crypttab_path = os.path.normpath("%s/etc/crypttab" % sysroot)
        crypttab = self.crypttab()
        origmask = os.umask(0o077)
        open(crypttab_path, "w").write(crypttab)
        os.umask(origmask)

        # /etc/mdadm.conf
        mdadm_path = os.path.normpath("%s/etc/mdadm.conf" % sysroot)
        mdadm_conf = self.mdadm_conf()
        if mdadm_conf:
            open(mdadm_path, "w").write(mdadm_conf)

        # /etc/multipath.conf
        if any(d for d in self.devices if d.type == "dm-multipath"):
            copy_to_system("/etc/multipath.conf")
            copy_to_system("/etc/multipath/wwids")
            copy_to_system("/etc/multipath/bindings")
        else:
            log.info("not writing out mpath configuration")

    def crypttab(self):
        # if we are upgrading, do we want to update crypttab?
        # gut reaction says no, but plymouth needs the names to be very
        # specific for passphrase prompting
        if not self.crypt_tab:
            self.crypt_tab = CryptTab(self.devicetree)
            self.crypt_tab.populate()

        devices = list(self.mountpoints.values()) + self.swap_devices

        # prune crypttab -- only mappings required by one or more entries
        for name in list(self.crypt_tab.mappings.keys()):
            keep = False
            map_info = self.crypt_tab[name]
            crypto_dev = map_info['device']
            for device in devices:
                if device == crypto_dev or device.depends_on(crypto_dev):
                    keep = True
                    break

            if not keep:
                del self.crypt_tab.mappings[name]

        return self.crypt_tab.crypttab()

    def mdadm_conf(self):
        """ Return the contents of mdadm.conf. """
        arrays = [d for d in self.devices if isinstance(d, MDRaidArrayDevice)]
        # Sort it, this not only looks nicer, but this will also put
        # containers (which get md0, md1, etc.) before their members
        # (which get md127, md126, etc.). and lame as it is mdadm will not
        # assemble the whole stack in one go unless listed in the proper order
        # in mdadm.conf
        arrays.sort(key=lambda d: d.path)
        if not arrays:
            return ""

        conf = "# mdadm.conf written out by anaconda\n"
        conf += "MAILADDR root\n"
        conf += "AUTO +imsm +1.x -all\n"
        devices = list(self.mountpoints.values()) + self.swap_devices
        for array in arrays:
            for device in devices:
                if device == array or device.depends_on(array):
                    conf += array.mdadm_conf_entry
                    break

        return conf

    def fstab(self):
        fmt_str = "%-23s %-23s %-7s %-15s %d %d\n"
        fstab = """
#
# /etc/fstab
# Created by anaconda on %s
#
# Accessible filesystems, by reference, are maintained under '/dev/disk/'.
# See man pages fstab(5), findfs(8), mount(8) and/or blkid(8) for more info.
#
# After editing this file, run 'systemctl daemon-reload' to update systemd
# units generated from this file.
#
""" % time.asctime()

        devices = sorted(self.mountpoints.values(),
                         key=lambda d: d.format.mountpoint)

        # filter swaps only in installer mode
        devices += [dev for dev in self.swap_devices if dev in self._fstab_swaps]

        netdevs = [d for d in self.devices if isinstance(d, NetworkStorageDevice)]

        rootdev = devices[0]
        root_on_netdev = any(rootdev.depends_on(netdev) for netdev in netdevs)

        for device in devices:
            # why the hell do we put swap in the fstab, anyway?
            if not device.format.mountable and device.format.type != "swap":
                continue

            # Don't write out lines for optical devices, either.
            if isinstance(device, OpticalDevice):
                continue

            fstype = getattr(device.format, "mount_type", device.format.type)
            if fstype == "swap":
                mountpoint = "swap"
                options = device.format.options
            else:
                mountpoint = device.format.mountpoint
                options = device.format.options
                if not mountpoint:
                    log.warning("%s filesystem on %s has no mountpoint",
                                fstype,
                                device.path)
                    continue

            options = options or "defaults"
            for netdev in netdevs:
                if device.depends_on(netdev):
                    if root_on_netdev and mountpoint == "/var":
                        options = options + ",x-initrd.mount"
                    break
            if device.encrypted:
                options += ",x-systemd.device-timeout=0"
            devspec = device.fstab_spec
            dump = device.format.dump
            if device.format.check and mountpoint == "/":
                passno = 1
            elif device.format.check:
                passno = 2
            else:
                passno = 0
            fstab = fstab + device.fstab_comment
            fstab = fstab + fmt_str % (devspec, mountpoint, fstype,
                                       options, dump, passno)

        # now, write out any lines we were unable to process because of
        # unrecognized filesystems or unresolveable device specifications
        for line in self.preserve_lines:
            fstab += line

        return fstab

    def add_fstab_swap(self, device):
        """
        Add swap device to the list of swaps that should appear in the fstab.

        :param device: swap device that should be added to the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self._fstab_swaps.add(device)

    def remove_fstab_swap(self, device):
        """
        Remove swap device from the list of swaps that should appear in the fstab.

        :param device: swap device that should be removed from the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        try:
            self._fstab_swaps.remove(device)
        except KeyError:
            pass

    def set_fstab_swaps(self, devices):
        """
        Set swap devices that should appear in the fstab.

        :param devices: iterable providing devices that should appear in the fstab
        :type devices: iterable providing blivet.devices.StorageDevice instances holding
                       a swap format

        """

        self._fstab_swaps = set(devices)


class Root(object):

    """ A Root represents an existing OS installation. """

    def __init__(self, mounts=None, swaps=None, name=None):
        """
            :keyword mounts: mountpoint dict
            :type mounts: dict (mountpoint keys and :class:`blivet.devices.StorageDevice` values)
            :keyword swaps: swap device list
            :type swaps: list of :class:`blivet.devices.StorageDevice`
            :keyword name: name for this installed OS
            :type name: str
        """
        # mountpoint key, StorageDevice value
        if not mounts:
            self.mounts = {}
        else:
            self.mounts = mounts

        # StorageDevice
        if not swaps:
            self.swaps = []
        else:
            self.swaps = swaps

        self.name = name    # eg: "Fedora Linux 16 for x86_64", "Linux on sda2"

        if not self.name and "/" in self.mounts:
            self.name = self.mounts["/"].format.uuid

    @property
    def device(self):
        return self.mounts.get("/")


class BlkidTab(object):

    """ Dictionary-like interface to blkid.tab with device path keys """

    def __init__(self, chroot=""):
        self.chroot = chroot
        self.devices = {}

    def parse(self):
        path = "%s/etc/blkid/blkid.tab" % self.chroot
        if not os.access(path, os.R_OK):
            return

        log.debug("parsing %s", path)
        with open(path) as f:
            for line in f.readlines():
                # this is pretty ugly, but an XML parser is more work than
                # is justifiable for this purpose
                if not line.startswith("<device "):
                    continue

                line = line[len("<device "):-len("</device>\n")]

                (data, _sep, device) = line.partition(">")
                if not device:
                    continue

                self.devices[device] = {}
                for pair in data.split():
                    try:
                        (key, value) = pair.split("=")
                    except ValueError:
                        continue

                    self.devices[device][key] = value[1:-1]  # strip off quotes

    def __getitem__(self, key):
        return self.devices[key]

    def get(self, key, default=None):
        return self.devices.get(key, default)


class CryptTab(object):

    """ Dictionary-like interface to crypttab entries with map name keys """

    def __init__(self, devicetree, blkid_tab=None, chroot=""):
        self.devicetree = devicetree
        self.blkid_tab = blkid_tab
        self.chroot = chroot
        self.mappings = {}

    def parse(self, chroot=""):
        """ Parse /etc/crypttab from an existing installation. """
        if not chroot or not os.path.isdir(chroot):
            chroot = ""

        path = "%s/etc/crypttab" % chroot
        if not os.access(path, os.R_OK):
            return

        log.debug("parsing %s", path)
        with open(path) as f:
            if not self.blkid_tab:
                try:
                    self.blkid_tab = BlkidTab(chroot=chroot)
                    self.blkid_tab.parse()
                except Exception:  # pylint: disable=broad-except
                    log_exception_info(fmt_str="failed to parse blkid.tab")
                    self.blkid_tab = None

            for line in f.readlines():
                (line, _pound, _comment) = line.partition("#")
                fields = line.split()
                if not 2 <= len(fields) <= 4:
                    continue
                elif len(fields) == 2:
                    fields.extend(['none', ''])
                elif len(fields) == 3:
                    fields.append('')

                (name, devspec, keyfile, options) = fields

                # resolve devspec to a device in the tree
                device = self.devicetree.resolve_device(devspec,
                                                        blkid_tab=self.blkid_tab)
                if device:
                    self.mappings[name] = {"device": device,
                                           "keyfile": keyfile,
                                           "options": options}

    def populate(self):
        """ Populate the instance based on the device tree's contents. """
        for device in self.devicetree.devices:
            # XXX should we put them all in there or just the ones that
            #     are part of a device containing swap or a filesystem?
            #
            #       Put them all in here -- we can filter from FSSet
            if device.format.type != "luks":
                continue

            key_file = device.format.key_file
            if not key_file:
                key_file = "none"

            options = device.format.options or ""

            self.mappings[device.format.map_name] = {"device": device,
                                                     "keyfile": key_file,
                                                     "options": options}

    def crypttab(self):
        """ Write out /etc/crypttab """
        crypttab = ""
        for name in self.mappings:
            entry = self[name]
            crypttab += "%s UUID=%s %s %s\n" % (name,
                                                entry['device'].format.uuid,
                                                entry['keyfile'],
                                                entry['options'])
        return crypttab

    def __getitem__(self, key):
        return self.mappings[key]

    def get(self, key, default=None):
        return self.mappings.get(key, default)


class InstallerStorage(Blivet):
    """ Top-level class for managing installer-related storage configuration. """
    def __init__(self, ksdata=None):
        """
            :keyword ksdata: kickstart data store
            :type ksdata: :class:`pykickstart.Handler`
        """
        super().__init__()

        self.ksdata = ksdata
        self._bootloader = None
        self.config = StorageDiscoveryConfig()
        self.autopart_type = AUTOPART_TYPE_LVM

        self.__luks_devs = {}
        self.fsset = FSSet(self.devicetree)
        self._free_space_snapshot = None
        self.live_backing_device = None

        self._short_product_name = shortProductName
        self._default_luks_version = DEFAULT_LUKS_VERSION

        self.autopart_luks_version = None
        self.autopart_pbkdf_args = None

    def copy(self):
        """Copy the storage.

        Kickstart data are not copied.
        """
        # Disable the kickstart data.
        old_data = self.ksdata
        self.ksdata = None

        # Create the copy.
        new_storage = super().copy()

        # Recover the kickstart data.
        self.ksdata = old_data
        new_storage.ksdata = old_data
        return new_storage

    def do_it(self, callbacks=None):
        """
        Commit queued changes to disk.

        :param callbacks: callbacks to be invoked when actions are executed
        :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_

        """
        super().do_it(callbacks=callbacks)

        # now set the boot partition's flag
        if self.bootloader and not self.bootloader.skip_bootloader:
            if self.bootloader.stage2_bootable:
                boot = self.boot_device
            else:
                boot = self.bootloader_device

            if boot.type == "mdarray":
                boot_devs = boot.parents
            else:
                boot_devs = [boot]

            for dev in boot_devs:
                if not hasattr(dev, "bootable"):
                    log.info("Skipping %s, not bootable", dev)
                    continue

                # Dos labels can only have one partition marked as active
                # and unmarking ie the windows partition is not a good idea
                skip = False
                if dev.disk.format.parted_disk.type == "msdos":
                    for p in dev.disk.format.parted_disk.partitions:
                        if p.type == parted.PARTITION_NORMAL and \
                           p.getFlag(parted.PARTITION_BOOT):
                            skip = True
                            break

                # GPT labeled disks should only have bootable set on the
                # EFI system partition (parted sets the EFI System GUID on
                # GPT partitions with the boot flag)
                if dev.disk.format.label_type == "gpt" and \
                   dev.format.type not in ["efi", "macefi"]:
                    skip = True

                if skip:
                    log.info("Skipping %s", dev.name)
                    continue

                # hfs+ partitions on gpt can't be marked bootable via parted
                if dev.disk.format.parted_disk.type != "gpt" or \
                        dev.format.type not in ["hfs+", "macefi"]:
                    log.info("setting boot flag on %s", dev.name)
                    dev.bootable = True

                # Set the boot partition's name on disk labels that support it
                if dev.parted_partition.disk.supportsFeature(parted.DISK_TYPE_PARTITION_NAME):
                    ped_partition = dev.parted_partition.getPedPartition()
                    ped_partition.set_name(dev.format.name)
                    log.info("Setting label on %s to '%s'", dev, dev.format.name)

                dev.disk.setup()
                dev.disk.format.commit_to_disk()

        self.dump_state("final")

    def write(self):
        sysroot = util.getSysroot()
        if not os.path.isdir("%s/etc" % sysroot):
            os.mkdir("%s/etc" % sysroot)

        self.make_mtab()
        self.fsset.write()
        iscsi.write(sysroot, self)
        fcoe.write(sysroot)

        if arch.is_s390():
            zfcp_proxy = STORAGE.get_proxy(ZFCP)
            zfcp_proxy.WriteConfiguration(sysroot)

        self.write_dasd_conf(sysroot)

    @property
    def bootloader(self):
        if self._bootloader is None:
            self._bootloader = get_bootloader()

        return self._bootloader

    def update_bootloader_disk_list(self):
        if not self.bootloader:
            return

        boot_disks = [d for d in self.disks if d.partitioned]
        boot_disks.sort(key=self.compare_disks_key)
        self.bootloader.set_disk_list(boot_disks)

    @property
    def boot_device(self):
        dev = None
        root_device = self.mountpoints.get("/")

        dev = self.mountpoints.get("/boot", root_device)
        return dev

    @property
    def default_boot_fstype(self):
        """The default filesystem type for the boot partition."""
        if self._default_boot_fstype:
            return self._default_boot_fstype

        fstype = None
        if self.bootloader:
            fstype = self.boot_fstypes[0]
        return fstype

    def set_default_boot_fstype(self, newtype):
        """ Set the default /boot fstype for this instance.

            Raise ValueError on invalid input.
        """
        log.debug("trying to set new default /boot fstype to '%s'", newtype)
        # This will raise ValueError if it isn't valid
        self._check_valid_fstype(newtype)
        self._default_boot_fstype = newtype

    @property
    def default_luks_version(self):
        """The default LUKS version."""
        return self._default_luks_version

    def set_default_luks_version(self, version):
        """Set the default LUKS version.

        :param version: a string with LUKS version
        :raises: ValueError on invalid input
        """
        log.debug("trying to set new default luks version to '%s'", version)
        self._check_valid_luks_version(version)
        self._default_luks_version = version

    def _check_valid_luks_version(self, version):
        get_format("luks", luks_version=version)

    def set_up_bootloader(self, early=False):
        """ Propagate ksdata into BootLoader.

            :keyword bool early: Set to True to skip stage1_device setup

            :raises BootloaderError: if stage1 setup fails

            If this needs to be run early, eg. to setup stage1_disk but
            not stage1_device 'early' should be set True to prevent
            it from raising BootloaderError
        """
        if not self.bootloader or not self.ksdata:
            log.warning("either ksdata or bootloader data missing")
            return

        if self.bootloader.skip_bootloader:
            log.info("user specified that bootloader install be skipped")
            return

        # Need to make sure that boot drive has been setup from the latest information.
        # This will also set self.bootloader.stage1_disk.
        self.ksdata.bootloader.execute(self, self.ksdata, None)

        self.bootloader.stage2_device = self.boot_device
        if not early:
            self.bootloader.set_stage1_device(self.devices)

    @property
    def bootloader_device(self):
        return getattr(self.bootloader, "stage1_device", None)

    @property
    def boot_fstypes(self):
        """A list of all valid filesystem types for the boot partition."""
        fstypes = []
        if self.bootloader:
            fstypes = self.bootloader.stage2_format_types
        return fstypes

    def get_fstype(self, mountpoint=None):
        """ Return the default filesystem type based on mountpoint. """
        fstype = super().get_fstype(mountpoint=mountpoint)

        if mountpoint == "/boot":
            fstype = self.default_boot_fstype

        return fstype

    @property
    def mountpoints(self):
        return self.fsset.mountpoints

    @property
    def root_device(self):
        return self.fsset.root_device

    @property
    def file_system_free_space(self):
        """ Combined free space in / and /usr as :class:`blivet.size.Size`. """
        mountpoints = ["/", "/usr"]
        free = Size(0)
        btrfs_volumes = []
        for mountpoint in mountpoints:
            device = self.mountpoints.get(mountpoint)
            if not device:
                continue

            # don't count the size of btrfs volumes repeatedly when multiple
            # subvolumes are present
            if isinstance(device, BTRFSSubVolumeDevice):
                if device.volume in btrfs_volumes:
                    continue
                else:
                    btrfs_volumes.append(device.volume)

            if device.format.exists:
                free += device.format.free
            else:
                free += device.format.free_space_estimate(device.size)

        return free

    @property
    def free_space_snapshot(self):
        # if no snapshot is available, do it now and return it
        self._free_space_snapshot = self._free_space_snapshot or self.get_free_space()

        return self._free_space_snapshot

    def create_free_space_snapshot(self):
        self._free_space_snapshot = self.get_free_space()

        return self._free_space_snapshot

    def get_free_space(self, disks=None, clear_part_type=None):  # pylint: disable=arguments-differ
        """ Return a dict with free space info for each disk.

             The dict values are 2-tuples: (disk_free, fs_free). fs_free is
             space available by shrinking filesystems. disk_free is space not
             allocated to any partition.

             disks and clear_part_type allow specifying a set of disks other than
             self.disks and a clear_part_type value other than
             self.config.clear_part_type.

             :keyword disks: overrides :attr:`disks`
             :type disks: list
             :keyword clear_part_type: overrides :attr:`self.config.clear_part_type`
             :type clear_part_type: int
             :returns: dict with disk name keys and tuple (disk, fs) free values
             :rtype: dict

            .. note::

                The free space values are :class:`blivet.size.Size` instances.

        """

        # FIXME: we should definitely do something with this method -- it takes
        # different parameters than get_free_space from Blivet and does
        # different things too

        if disks is None:
            disks = self.disks

        if clear_part_type is None:
            clear_part_type = self.config.clear_part_type

        free = {}
        for disk in disks:
            should_clear = self.should_clear(disk, clear_part_type=clear_part_type,
                                             clear_part_disks=[disk.name])
            if should_clear:
                free[disk.name] = (disk.size, Size(0))
                continue

            disk_free = Size(0)
            fs_free = Size(0)
            if disk.partitioned:
                disk_free = disk.format.free
                for partition in (p for p in self.partitions if p.disk == disk):
                    # only check actual filesystems since lvm &c require a bunch of
                    # operations to translate free filesystem space into free disk
                    # space
                    should_clear = self.should_clear(partition,
                                                     clear_part_type=clear_part_type,
                                                     clear_part_disks=[disk.name])
                    if should_clear:
                        disk_free += partition.size
                    elif hasattr(partition.format, "free"):
                        fs_free += partition.format.free
            elif hasattr(disk.format, "free"):
                fs_free = disk.format.free
            elif disk.format.type is None:
                disk_free = disk.size

            free[disk.name] = (disk_free, fs_free)

        return free

    def update_ksdata(self):
        """ Update ksdata to reflect the settings of this Blivet instance. """
        if not self.ksdata or not self.mountpoints:
            return

        # clear out whatever was there before
        self.ksdata.partition.partitions = []
        self.ksdata.logvol.lvList = []
        self.ksdata.raid.raidList = []
        self.ksdata.volgroup.vgList = []
        self.ksdata.btrfs.btrfsList = []

        # iscsi?
        # fcoe?
        # zfcp?
        # dmraid?

        # bootloader

        # disk selection
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)

        if self.ignored_disks:
            disk_select_proxy.SetIgnoredDisks(self.ignored_disks)
        elif self.exclusive_disks:
            disk_select_proxy.SetSelectedDisks(self.exclusive_disks)

        # autopart
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)
        auto_part_proxy.SetEnabled(self.do_autopart)
        auto_part_proxy.SetType(self.autopart_type)
        auto_part_proxy.SetEncrypted(self.encrypted_autopart)

        if self.encrypted_autopart:
            auto_part_proxy.SetLUKSVersion(self.autopart_luks_version)

            if self.autopart_pbkdf_args:
                auto_part_proxy.SetPBKDF(self.autopart_pbkdf_args.type or "")
                auto_part_proxy.SetPBKDFMemory(self.autopart_pbkdf_args.max_memory_kb)
                auto_part_proxy.SetPBKDFIterations(self.autopart_pbkdf_args.iterations)
                auto_part_proxy.SetPBKDFTime(self.autopart_pbkdf_args.time_ms)

        # clearpart
        disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        disk_init_proxy.SetInitializationMode(self.config.clear_part_type)
        disk_init_proxy.SetDrivesToClear(self.config.clear_part_disks)
        disk_init_proxy.SetDevicesToClear(self.config.clear_part_devices)
        disk_init_proxy.SetInitializeLabelsEnabled(self.config.initialize_disks)

        if disk_init_proxy.InitializationMode == CLEAR_PARTITIONS_NONE:
            # Make a list of initialized disks and of removed partitions. If any
            # partitions were removed from disks that were not completely
            # cleared we'll have to use CLEAR_PARTITIONS_LIST and provide a list
            # of all removed partitions. If no partitions were removed from a
            # disk that was not cleared/reinitialized we can use
            # CLEAR_PARTITIONS_ALL.
            disk_init_proxy.SetDrivesToClear([])
            disk_init_proxy.SetDevicesToClear([])

            fresh_disks = [d.name for d in self.disks if d.partitioned and
                           not d.format.exists]

            destroy_actions = self.devicetree.actions.find(action_type="destroy",
                                                           object_type="device")

            cleared_partitions = []
            partial = False
            for action in destroy_actions:
                if action.device.type == "partition":
                    if action.device.disk.name not in fresh_disks:
                        partial = True

                    cleared_partitions.append(action.device.name)

            if not destroy_actions:
                pass
            elif partial:
                # make a list of removed partitions
                disk_init_proxy.SetInitializationMode(CLEAR_PARTITIONS_LIST)
                disk_init_proxy.SetDevicesToClear(cleared_partitions)
            else:
                # if they didn't partially clear any disks, use the shorthand
                disk_init_proxy.SetInitializationMode(CLEAR_PARTITIONS_ALL)
                disk_init_proxy.SetDrivesToClear(fresh_disks)

        if self.do_autopart:
            return

        self._update_custom_storage_ksdata()

    def _update_custom_storage_ksdata(self):
        """ Update KSData for custom storage. """

        # custom storage
        ks_map = {PartitionDevice: ("PartData", "partition"),
                  TmpFSDevice: ("PartData", "partition"),
                  LVMLogicalVolumeDevice: ("LogVolData", "logvol"),
                  LVMVolumeGroupDevice: ("VolGroupData", "volgroup"),
                  MDRaidArrayDevice: ("RaidData", "raid"),
                  BTRFSDevice: ("BTRFSData", "btrfs")}

        # list comprehension that builds device ancestors should not get None as a member
        # when searching for bootloader devices
        bootloader_devices = []
        if self.bootloader_device is not None:
            bootloader_devices.append(self.bootloader_device)

        # biosboot is a special case
        for device in self.devices:
            if device.format.type == 'biosboot':
                bootloader_devices.append(device)

        # make a list of ancestors of all used devices
        devices = list(set(a for d in list(self.mountpoints.values()) + self.swaps + bootloader_devices
                           for a in d.ancestors))

        # devices which share information with their distinct raw device
        complementary_devices = [d for d in devices if d.raw_device is not d]

        devices.sort(key=lambda d: len(d.ancestors))
        for device in devices:
            cls = next((c for c in ks_map if isinstance(device, c)), None)
            if cls is None:
                log.info("omitting ksdata: %s", device)
                continue

            class_attr, list_attr = ks_map[cls]

            cls = getattr(self.ksdata, class_attr)
            data = cls()    # all defaults

            complements = [d for d in complementary_devices if d.raw_device is device]

            if len(complements) > 1:
                log.warning("omitting ksdata for %s, found too many (%d) complementary devices", device, len(complements))
                continue

            device = complements[0] if complements else device

            device.populate_ksdata(data)

            parent = getattr(self.ksdata, list_attr)
            parent.dataList().append(data)

    def shutdown(self):
        """ Deactivate all devices. """
        try:
            self.devicetree.teardown_all()
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.error, "failure tearing down device tree")

    def reset(self, cleanup_only=False):
        """ Reset storage configuration to reflect actual system state.

            This will cancel any queued actions and rescan from scratch but not
            clobber user-obtained information like passphrases, iscsi config, &c

            :keyword cleanup_only: prepare the tree only to deactivate devices
            :type cleanup_only: bool

            See :meth:`devicetree.Devicetree.populate` for more information
            about the cleanup_only keyword argument.
        """
        # save passphrases for luks devices so we don't have to reprompt
        self.encryption_passphrase = None
        for device in self.devices:
            if device.format.type == "luks" and device.format.exists:
                self.save_passphrase(device)

        if self.ksdata:
            nvdimm_ksdata = self.ksdata.nvdimm
        else:
            nvdimm_ksdata = None
        ignored_nvdimm_devs = get_ignored_nvdimm_blockdevs(nvdimm_ksdata)
        if ignored_nvdimm_devs:
            log.debug("adding NVDIMM devices %s to ignored disks",
                        ",".join(ignored_nvdimm_devs))

        if self.ksdata:
            disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
            if ignored_nvdimm_devs:
                ignored_disks = disk_select_proxy.IgnoredDisks
                ignored_disks.extend(ignored_nvdimm_devs)
                disk_select_proxy.SetIgnoredDisks(ignored_disks)
            self.config.update()

            self.ignored_disks = disk_select_proxy.IgnoredDisks
            self.exclusive_disks = disk_select_proxy.SelectedDisks
        else:
            self.ignored_disks.extend(ignored_nvdimm_devs)

        if not flags.imageInstall:
            iscsi.startup()
            fcoe.startup()

            if arch.is_s390():
                zfcp_proxy = STORAGE.get_proxy(ZFCP)
                zfcp_proxy.ReloadModule()

        super().reset(cleanup_only=cleanup_only)

        self.fsset = FSSet(self.devicetree)

        if self.bootloader:
            # clear out bootloader attributes that refer to devices that are
            # no longer in the tree
            self.bootloader.reset()

        self.update_bootloader_disk_list()

        # protected device handling
        self.protected_dev_names = []
        self._resolve_protected_device_specs()
        self._find_live_backing_device()
        for devname in self.protected_dev_names:
            dev = self.devicetree.get_device_by_name(devname, hidden=True)
            self._mark_protected_device(dev)

        self.roots = []
        self.roots = find_existing_installations(self.devicetree)
        self.dump_state("initial")

    def _resolve_protected_device_specs(self):
        """ Resolve the protected device specs to device names. """
        for spec in self.config.protected_dev_specs:
            dev = self.devicetree.resolve_device(spec)
            if dev is not None:
                log.debug("protected device spec %s resolved to %s", spec, dev.name)
                self.protected_dev_names.append(dev.name)

    def _find_live_backing_device(self):
        # FIXME: the backing dev for the live image can't be used as an
        # install target.  note that this is a little bit of a hack
        # since we're assuming that /run/initramfs/live will exist
        for mnt in open("/proc/mounts").readlines():
            if " /run/initramfs/live " not in mnt:
                continue

            live_device_path = mnt.split()[0]
            udev_device = udev.get_device(device_node=live_device_path)
            if udev_device and udev.device_is_partition(udev_device):
                live_device_name = udev.device_get_partition_disk(udev_device)
            else:
                live_device_name = live_device_path.split("/")[-1]

            log.info("resolved live device to %s", live_device_name)
            if live_device_name:
                log.info("marking live device %s protected", live_device_name)
                self.protected_dev_names.append(live_device_name)
                self.live_backing_device = live_device_name

            break

    def _mark_protected_device(self, device):
        """
          If this device is protected, mark it as such now. Once the tree
          has been populated, devices' protected attribute is how we will
          identify protected devices.

         :param :class: `blivet.devices.storage.StorageDevice` device: device to
          mark as protected
        """
        if device.name in self.protected_dev_names:
            device.protected = True
            # if this is the live backing device we want to mark its parents
            # as protected also
            if device.name == self.live_backing_device:
                for parent in device.parents:
                    parent.protected = True

    def empty_device(self, device):
        empty = True
        if device.partitioned:
            partitions = device.children
            empty = all([p.is_magic for p in partitions])
        else:
            empty = (device.format.type is None)

        return empty

    @property
    def unused_devices(self):
        used_devices = []
        for root in self.roots:
            for device in list(root.mounts.values()) + root.swaps:
                if device not in self.devices:
                    continue

                used_devices.extend(device.ancestors)

        for new in [d for d in self.devicetree.leaves if not d.format.exists]:
            if new.format.mountable and not new.format.mountpoint:
                continue

            used_devices.extend(new.ancestors)

        for device in self.partitions:
            if getattr(device, "is_logical", False):
                extended = device.disk.format.extended_partition.path
                used_devices.append(self.devicetree.get_device_by_path(extended))

        used = set(used_devices)
        _all = set(self.devices)
        return list(_all.difference(used))

    def should_clear(self, device, **kwargs):
        """ Return True if a clearpart settings say a device should be cleared.

            :param device: the device (required)
            :type device: :class:`blivet.devices.StorageDevice`
            :keyword clear_part_type: overrides :attr:`self.config.clear_part_type`
            :type clear_part_type: int
            :keyword clear_part_disks: overrides
                                     :attr:`self.config.clear_part_disks`
            :type clear_part_disks: list
            :keyword clear_part_devices: overrides
                                       :attr:`self.config.clear_part_devices`
            :type clear_part_devices: list
            :returns: whether or not clear_partitions should remove this device
            :rtype: bool
        """
        clear_part_type = kwargs.get("clear_part_type", self.config.clear_part_type)
        clear_part_disks = kwargs.get("clear_part_disks",
                                      self.config.clear_part_disks)
        clear_part_devices = kwargs.get("clear_part_devices",
                                        self.config.clear_part_devices)

        for disk in device.disks:
            # this will not include disks with hidden formats like multipath
            # and firmware raid member disks
            if clear_part_disks and disk.name not in clear_part_disks:
                return False

        if not self.config.clear_non_existent:
            if (device.is_disk and not device.format.exists) or \
               (not device.is_disk and not device.exists):
                return False

        # the only devices we want to clear when clear_part_type is
        # CLEAR_PARTITIONS_NONE are uninitialized disks, or disks with no
        # partitions, in clear_part_disks, and then only when we have been asked
        # to initialize disks as needed
        if clear_part_type in [CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_DEFAULT]:
            if not self.config.initialize_disks or not device.is_disk:
                return False

            if not self.empty_device(device):
                return False

        if isinstance(device, PartitionDevice):
            # Never clear the special first partition on a Mac disk label, as
            # that holds the partition table itself.
            # Something similar for the third partition on a Sun disklabel.
            if device.is_magic:
                return False

            # We don't want to fool with extended partitions, freespace, &c
            if not device.is_primary and not device.is_logical:
                return False

            if clear_part_type == CLEAR_PARTITIONS_LINUX and \
               not device.format.linux_native and \
               not device.get_flag(parted.PARTITION_LVM) and \
               not device.get_flag(parted.PARTITION_RAID) and \
               not device.get_flag(parted.PARTITION_SWAP):
                return False
        elif device.is_disk:
            if device.partitioned and clear_part_type != CLEAR_PARTITIONS_ALL:
                # if clear_part_type is not CLEAR_PARTITIONS_ALL but we'll still be
                # removing every partition from the disk, return True since we
                # will want to be able to create a new disklabel on this disk
                if not self.empty_device(device):
                    return False

            # Never clear disks with hidden formats
            if device.format.hidden:
                return False

            # When clear_part_type is CLEAR_PARTITIONS_LINUX and a disk has non-
            # linux whole-disk formatting, do not clear it. The exception is
            # the case of an uninitialized disk when we've been asked to
            # initialize disks as needed
            if (clear_part_type == CLEAR_PARTITIONS_LINUX and
                not ((self.config.initialize_disks and
                      self.empty_device(device)) or
                     (not device.partitioned and device.format.linux_native))):
                return False

        # Don't clear devices holding install media.
        descendants = self.devicetree.get_dependent_devices(device)
        if device.protected or any(d.protected for d in descendants):
            return False

        if clear_part_type == CLEAR_PARTITIONS_LIST and \
           device.name not in clear_part_devices:
            return False

        return True

    def clear_partitions(self):
        """ Clear partitions and dependent devices from disks.

            This is also where zerombr is handled.
        """
        # Sort partitions by descending partition number to minimize confusing
        # things like multiple "destroy sda5" actions due to parted renumbering
        # partitions. This can still happen through the UI but it makes sense to
        # avoid it where possible.
        partitions = sorted(self.partitions,
                            key=lambda p: getattr(p.parted_partition, "number", 1),
                            reverse=True)
        for part in partitions:
            log.debug("clearpart: looking at %s", part.name)
            if not self.should_clear(part):
                continue

            self.recursive_remove(part)
            log.debug("partitions: %s", [p.name for p in part.disk.children])

        # now remove any empty extended partitions
        self.remove_empty_extended_partitions()

        # ensure all disks have appropriate disklabels
        for disk in self.disks:
            zerombr = (self.config.zero_mbr and disk.format.type is None)
            should_clear = self.should_clear(disk)
            if should_clear:
                self.recursive_remove(disk)

            if zerombr or should_clear:
                if disk.protected:
                    log.warning("cannot clear '%s': disk is protected or read only", disk.name)
                else:
                    log.debug("clearpart: initializing %s", disk.name)
                    self.initialize_disk(disk)

        self.update_bootloader_disk_list()

    def _get_hostname(self):
        """Return a hostname."""
        ignored_hostnames = {None, "", 'localhost', 'localhost.localdomain'}

        network_proxy = NETWORK.get_proxy()
        hostname = network_proxy.Hostname

        if hostname in ignored_hostnames:
            hostname = network_proxy.GetCurrentHostname()

        if hostname in ignored_hostnames:
            hostname = None

        return hostname

    def _get_container_name_template(self, prefix=None):
        """Return a template for suggest_container_name method."""
        prefix = prefix or ""  # make sure prefix is a string instead of None

        # try to create a device name incorporating the hostname
        hostname = self._get_hostname()

        if hostname:
            template = "%s_%s" % (prefix, hostname.split('.')[0].lower())
            template = self.safe_device_name(template)
        else:
            template = prefix

        if flags.imageInstall:
            template = "%s_image" % template

        return template

    def format_by_default(self, device):
        """Return whether the device should be reformatted by default."""
        formatlist = ['/boot', '/var', '/tmp', '/usr']
        exceptlist = ['/home', '/usr/local', '/opt', '/var/www']

        if not device.format.linux_native:
            return False

        if device.format.mountable:
            if not device.format.mountpoint:
                return False

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

    def must_format(self, device):
        """ Return a string explaining why the device must be reformatted.

            Return None if the device need not be reformatted.
        """
        if device.format.mountable and device.format.mountpoint == "/":
            return _("You must create a new file system on the root device.")

        return None

    def turn_on_swap(self):
        self.fsset.turn_on_swap(root_path=util.getSysroot())

    def mount_filesystems(self, read_only=None, skip_root=False):
        self.fsset.mount_filesystems(root_path=util.getSysroot(),
                                     read_only=read_only, skip_root=skip_root)

    def umount_filesystems(self, swapoff=True):
        self.fsset.umount_filesystems(swapoff=swapoff)

    def parse_fstab(self, chroot=None):
        self.fsset.parse_fstab(chroot=chroot)

    def mk_dev_root(self):
        self.fsset.mk_dev_root()

    def create_swap_file(self, device, size):
        self.fsset.create_swap_file(device, size)

    def write_dasd_conf(self, root):
        """ Write /etc/dasd.conf to target system for all DASD devices
            configured during installation.
        """
        dasds = [d for d in self.devices if d.type == "dasd"]
        dasds.sort(key=lambda d: d.name)
        if not (arch.is_s390() and dasds):
            return

        with open(os.path.realpath(root + "/etc/dasd.conf"), "w") as f:
            for dasd in dasds:
                fields = [dasd.busid] + dasd.get_opts()
                f.write("%s\n" % " ".join(fields),)

        # check for hyper PAV aliases; they need to get added to dasd.conf as well
        sysfs = "/sys/bus/ccw/drivers/dasd-eckd"

        # in the case that someone is installing with *only* FBA DASDs,the above
        # sysfs path will not exist; so check for it and just bail out of here if
        # that's the case
        if not os.path.exists(sysfs):
            return

        # this does catch every DASD, even non-aliases, but we're only going to be
        # checking for a very specific flag, so there won't be any duplicate entries
        # in dasd.conf
        devs = [d for d in os.listdir(sysfs) if d.startswith("0.0")]
        with open(os.path.realpath(root + "/etc/dasd.conf"), "a") as f:
            for d in devs:
                aliasfile = "%s/%s/alias" % (sysfs, d)
                with open(aliasfile, "r") as falias:
                    alias = falias.read().strip()

                # if alias == 1, then the device is an alias; otherwise it is a
                # normal dasd (alias == 0) and we can skip it, since it will have
                # been added to dasd.conf in the above block of code
                if alias == "1":
                    f.write("%s\n" % d)

    def make_mtab(self):
        path = "/etc/mtab"
        target = "/proc/self/mounts"
        path = os.path.normpath("%s/%s" % (util.getSysroot(), path))

        if os.path.islink(path):
            # return early if the mtab symlink is already how we like it
            current_target = os.path.normpath(os.path.dirname(path) +
                                              "/" + os.readlink(path))
            if current_target == target:
                return

        if os.path.exists(path):
            os.unlink(path)

        os.symlink(target, path)

    def add_fstab_swap(self, device):
        """
        Add swap device to the list of swaps that should appear in the fstab.

        :param device: swap device that should be added to the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self.fsset.add_fstab_swap(device)

    def remove_fstab_swap(self, device):
        """
        Remove swap device from the list of swaps that should appear in the fstab.

        :param device: swap device that should be removed from the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self.fsset.remove_fstab_swap(device)

    def set_fstab_swaps(self, devices):
        """
        Set swap devices that should appear in the fstab.

        :param devices: iterable providing devices that should appear in the fstab
        :type devices: iterable providing blivet.devices.StorageDevice instances holding
                       a swap format

        """

        self.fsset.set_fstab_swaps(devices)


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
    except Exception:  # pylint: disable=broad-except
        log_exception_info(fmt_str="failed to find device name for path %s", fmt_args=[path])
        return None

    if device_name.startswith("dm-"):
        # have I told you lately that I love you, device-mapper?
        device_name = blockdev.dm.name_from_node(device_name)

    return devicetree.get_device_by_name(device_name)


def turn_on_filesystems(storage, mount_only=False, callbacks=None):
    """
    Perform installer-specific activation of storage configuration.

    :param callbacks: callbacks to be invoked when actions are executed
    :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_register`

    """
    if not mount_only:
        if (flags.livecdInstall and not flags.imageInstall and not storage.fsset.active):
            # turn off any swaps that we didn't turn on
            # needed for live installs
            blivet_util.run_program(["swapoff", "-a"])
        storage.devicetree.teardown_all()

        try:
            storage.do_it(callbacks)
        except (FSResizeError, FormatResizeError) as e:
            if error_handler.cb(e) == ERROR_RAISE:
                raise

        storage.turn_on_swap()
    # FIXME:  For livecd, skip_root needs to be True.
    storage.mount_filesystems()

    if not mount_only:
        write_escrow_packets(storage)


def write_escrow_packets(storage):
    escrow_devices = [d for d in storage.devices if d.format.type == 'luks' and
                      d.format.escrow_cert]

    if not escrow_devices:
        return

    log.debug("escrow: write_escrow_packets start")

    backup_passphrase = blockdev.crypto.generate_backup_passphrase()

    try:
        escrow_dir = util.getSysroot() + "/root"
        log.debug("escrow: writing escrow packets to %s", escrow_dir)
        blivet_util.makedirs(escrow_dir)
        for device in escrow_devices:
            log.debug("escrow: device %s: %s",
                      repr(device.path), repr(device.format.type))
            device.format.escrow(escrow_dir,
                                 backup_passphrase)

    except (IOError, RuntimeError) as e:
        # TODO: real error handling
        log.error("failed to store encryption key: %s", e)

    log.debug("escrow: write_escrow_packets done")

def get_ignored_nvdimm_blockdevs(nvdimm_ksdata):
    """Return names of nvdimm devices to be ignored.

    By default nvdimm devices are ignored. To become available for installation,
    the device(s) must be specified by nvdimm kickstart command.
    Also, only devices in sector mode are allowed.

    :param nvdimm_ksdata: nvdimm kickstart data
    :type nvdimm_ksdata: Nvdimm kickstart command
    :returns: names of nvdimm block devices that should be ignored for installation
    :rtype: set(str)
    """

    ks_allowed_namespaces = set()
    ks_allowed_blockdevs = set()
    if nvdimm_ksdata:
        # Gather allowed blockdev names and namespaces
        for action in nvdimm_ksdata.actionList:
            if action.action == NVDIMM_ACTION_USE:
                if action.namespace:
                    ks_allowed_namespaces.add(action.namespace)
                if action.blockdevs:
                    ks_allowed_blockdevs.update(action.blockdevs)
            if action.action == NVDIMM_ACTION_RECONFIGURE:
                ks_allowed_namespaces.add(action.namespace)

    ignored_blockdevs = set()
    for ns_name, ns_info in nvdimm.namespaces.items():
        if ns_info.mode != blockdev.NVDIMMNamespaceMode.SECTOR:
            log.debug("%s / %s will be ignored - NVDIMM device is not in sector mode",
                      ns_name, ns_info.blockdev)
        else:
            if ns_name in ks_allowed_namespaces or \
                    ns_info.blockdev in ks_allowed_blockdevs:
                continue
            else:
                log.debug("%s / %s will be ignored - NVDIMM device has not been configured to be used",
                          ns_name, ns_info.blockdev)
        if ns_info.blockdev:
            ignored_blockdevs.add(ns_info.blockdev)

    return ignored_blockdevs

def storage_initialize(storage, ksdata, protected):
    """ Perform installer-specific storage initialization. """
    update_blivet_flags(blivet_flags, flags)

    # Platform class setup depends on flags, re-initialize it.
    _platform.update_from_flags()

    storage.shutdown()

    # Set up the protected partitions list now.
    if protected:
        storage.config.protected_dev_specs.extend(protected)

    while True:
        try:
            # This also calls storage.config.update().
            storage.reset()
        except StorageError as e:
            if error_handler.cb(e) == ERROR_RAISE:
                raise
            else:
                continue
        else:
            break

    if protected and not flags.livecdInstall and \
       not any(d.protected for d in storage.devices):
        raise UnknownSourceDeviceError(protected)

    # kickstart uses all the disks
    if flags.automatedInstall:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        ignored_disks = disk_select_proxy.IgnoredDisks

        if not selected_disks:
            selected_disks = [d.name for d in storage.disks if d.name not in ignored_disks]
            disk_select_proxy.SetSelectedDisks(selected_disks)
            log.debug("onlyuse is now: %s", ",".join(selected_disks))


def mount_existing_system(fsset, root_device, read_only=None):
    """ Mount filesystems specified in root_device's /etc/fstab file. """
    root_path = util.getSysroot()

    read_only = "ro" if read_only else ""

    if root_device.protected and os.path.ismount("/mnt/install/isodir"):
        blivet_util.mount("/mnt/install/isodir",
                          root_path,
                          fstype=root_device.format.type,
                          options="bind")
    else:
        root_device.setup()
        root_device.format.mount(chroot=root_path,
                                 mountpoint="/",
                                 options="%s,%s" % (root_device.format.options, read_only))

    fsset.parse_fstab()
    fsset.mount_filesystems(root_path=root_path, read_only=read_only, skip_root=True)
