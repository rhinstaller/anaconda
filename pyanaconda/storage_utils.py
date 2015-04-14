#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""UI-independent storage utility functions"""

import re
import locale

from contextlib import contextmanager

from blivet import arch
from blivet import util
from blivet.size import Size
from blivet.platform import platform as _platform
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_DISK

from pyanaconda.i18n import _, N_
from pyanaconda import isys
from pyanaconda.constants import productName

from pykickstart.constants import AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS
from pykickstart.constants import AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

import logging
log = logging.getLogger("anaconda")

# TODO: all those constants and mappings should go to blivet
DEVICE_TEXT_LVM = N_("LVM")
DEVICE_TEXT_LVM_THINP = N_("LVM Thin Provisioning")
DEVICE_TEXT_MD = N_("RAID")
DEVICE_TEXT_PARTITION = N_("Standard Partition")
DEVICE_TEXT_BTRFS = N_("Btrfs")
DEVICE_TEXT_DISK = N_("Disk")

DEVICE_TEXT_MAP = {DEVICE_TYPE_LVM: DEVICE_TEXT_LVM,
                   DEVICE_TYPE_MD: DEVICE_TEXT_MD,
                   DEVICE_TYPE_PARTITION: DEVICE_TEXT_PARTITION,
                   DEVICE_TYPE_BTRFS: DEVICE_TEXT_BTRFS,
                   DEVICE_TYPE_LVM_THINP: DEVICE_TEXT_LVM_THINP,
                   DEVICE_TYPE_DISK: DEVICE_TEXT_DISK}

PARTITION_ONLY_FORMAT_TYPES = ("macefi", "prepboot", "biosboot", "appleboot")

MOUNTPOINT_DESCRIPTIONS = {"Swap": N_("The 'swap' area on your computer is used by the operating\n"
                                      "system when running low on memory."),
                           "Boot": N_("The 'boot' area on your computer is where files needed\n"
                                      "to start the operating system are stored."),
                           "Root": N_("The 'root' area on your computer is where core system\n"
                                      "files and applications are stored."),
                           "Home": N_("The 'home' area on your computer is where all your personal\n"
                                      "data is stored."),
                           "BIOS Boot": N_("The BIOS boot partition is required to enable booting\n"
                                           "from GPT-partitioned disks on BIOS hardware."),
                           "PReP Boot": N_("The PReP boot partition is required as part of the\n"
                                           "boot loader configuration on some PPC platforms.")
                            }

AUTOPART_CHOICES = ((N_("Standard Partition"), AUTOPART_TYPE_PLAIN),
                    (N_("Btrfs"), AUTOPART_TYPE_BTRFS),
                    (N_("LVM"), AUTOPART_TYPE_LVM),
                    (N_("LVM Thin Provisioning"), AUTOPART_TYPE_LVM_THINP))

AUTOPART_DEVICE_TYPES = {AUTOPART_TYPE_LVM: DEVICE_TYPE_LVM,
                         AUTOPART_TYPE_LVM_THINP: DEVICE_TYPE_LVM_THINP,
                         AUTOPART_TYPE_PLAIN: DEVICE_TYPE_PARTITION,
                         AUTOPART_TYPE_BTRFS: DEVICE_TYPE_BTRFS}

NAMED_DEVICE_TYPES = (DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM, DEVICE_TYPE_MD, DEVICE_TYPE_LVM_THINP)
CONTAINER_DEVICE_TYPES = (DEVICE_TYPE_LVM, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP)

def size_from_input(input_str, units=None):
    """ Get a Size object from an input string.

        :param str input_str: a string forming some representation of a size
        :param units: use these units if none specified in input_str
        :type units: str or NoneType
        :returns: a Size object corresponding to input_str
        :rtype: :class:`blivet.size.Size` or NoneType

        Units default to bytes if no units in input_str or units.
    """

    if not input_str:
        # Nothing to parse
        return None

    # A string ending with a digit contains no units information.
    if re.search(r'[\d.%s]$' % locale.nl_langinfo(locale.RADIXCHAR), input_str):
        input_str += units or ""

    try:
        size = Size(input_str)
    except ValueError:
        return None

    return size

def device_type_from_autopart(autopart_type):
    """Get device type matching the given autopart type."""

    return AUTOPART_DEVICE_TYPES.get(autopart_type, None)

class UIStorageFilter(logging.Filter):
    """Logging filter for UI storage events"""

    def filter(self, record):
        record.name = "storage.ui"
        return True

@contextmanager
def ui_storage_logger():
    """Context manager that applies the UIStorageFilter for its block"""

    storage_log = logging.getLogger("blivet")
    storage_filter = UIStorageFilter()
    storage_log.addFilter(storage_filter)
    yield
    storage_log.removeFilter(storage_filter)

class SanityException(Exception):
    pass

class SanityError(SanityException):
    pass

class SanityWarning(SanityException):
    pass

class LUKSDeviceWithoutKeyError(SanityError):
    pass

def sanity_check(storage, min_ram=isys.MIN_RAM):
    """
    Run a series of tests to verify the storage configuration.

    This function is called at the end of partitioning so that
    we can make sure you don't have anything silly (like no /,
    a really small /, etc).

    :param storage: an instance of the :class:`blivet.Blivet` class to check
    :param min_ram: minimum RAM (in MiB) needed for the installation with swap
                    space available
    :rtype: a list of SanityExceptions
    :return: a list of accumulated errors and warnings

    """

    exns = []

    checkSizes = [('/usr', Size("250 MiB")), ('/tmp', Size("50 MiB")), ('/var', Size("384 MiB")),
                  ('/home', Size("100 MiB")), ('/boot', Size("200 MiB"))]
    mustbeonlinuxfs = ['/', '/var', '/tmp', '/usr', '/home', '/usr/share', '/usr/lib']
    mustbeonroot = ['/bin','/dev','/sbin','/etc','/lib','/root', '/mnt', 'lost+found', '/proc']

    filesystems = storage.mountpoints
    root = storage.fsset.rootDevice
    swaps = storage.fsset.swapDevices

    if root:
        if root.size < Size("250 MiB"):
            exns.append(
               SanityWarning(_("Your root partition is less than 250 "
                              "megabytes which is usually too small to "
                              "install %s.") % (productName,)))
    else:
        exns.append(
           SanityError(_("You have not defined a root partition (/), "
                        "which is required for installation of %s "
                        "to continue.") % (productName,)))

    # Prevent users from installing on s390x with (a) no /boot volume, (b) the
    # root volume on LVM, and (c) the root volume not restricted to a single
    # PV
    # NOTE: There is not really a way for users to create a / volume
    # restricted to a single PV.  The backend support is there, but there are
    # no UI hook-ups to drive that functionality, but I do not personally
    # care.  --dcantrell
    if arch.isS390() and '/boot' not in storage.mountpoints and root:
        if root.type == 'lvmlv' and not root.singlePV:
            exns.append(
               SanityError(_("This platform requires /boot on a dedicated "
                            "partition or logical volume.  If you do not "
                            "want a /boot volume, you must place / on a "
                            "dedicated non-LVM partition.")))

    # FIXME: put a check here for enough space on the filesystems. maybe?

    for (mount, size) in checkSizes:
        if mount in filesystems and filesystems[mount].size < size:
            exns.append(
               SanityWarning(_("Your %(mount)s partition is less than "
                              "%(size)s which is lower than recommended "
                              "for a normal %(productName)s install.")
                            % {'mount': mount, 'size': size,
                               'productName': productName}))

    for (mount, device) in filesystems.items():
        problem = filesystems[mount].checkSize()
        if problem < 0:
            exns.append(
               SanityError(_("Your %(mount)s partition is too small for %(format)s formatting "
                            "(allowable size is %(minSize)s to %(maxSize)s)")
                          % {"mount": mount, "format": device.format.name,
                             "minSize": device.minSize, "maxSize": device.maxSize}))
        elif problem > 0:
            exns.append(
               SanityError(_("Your %(mount)s partition is too large for %(format)s formatting "
                            "(allowable size is %(minSize)s to %(maxSize)s)")
                          % {"mount":mount, "format": device.format.name,
                             "minSize": device.minSize, "maxSize": device.maxSize}))

    if storage.bootloader and not storage.bootloader.skip_bootloader:
        stage1 = storage.bootloader.stage1_device
        if not stage1:
            exns.append(
               SanityError(_("No valid boot loader target device found. "
                            "See below for details.")))
            pe = _platform.stage1MissingError
            if pe:
                exns.append(SanityError(_(pe)))
        else:
            storage.bootloader.is_valid_stage1_device(stage1)
            exns.extend(SanityError(msg) for msg in storage.bootloader.errors)
            exns.extend(SanityWarning(msg) for msg in storage.bootloader.warnings)

        stage2 = storage.bootloader.stage2_device
        if stage1 and not stage2:
            exns.append(SanityError(_("You have not created a bootable partition.")))
        else:
            storage.bootloader.is_valid_stage2_device(stage2)
            exns.extend(SanityError(msg) for msg in storage.bootloader.errors)
            exns.extend(SanityWarning(msg) for msg in storage.bootloader.warnings)
            if not storage.bootloader.check():
                exns.extend(SanityError(msg) for msg in storage.bootloader.errors)

        #
        # check that GPT boot disk on BIOS system has a BIOS boot partition
        #
        if _platform.weight(fstype="biosboot") and \
           stage1 and stage1.isDisk and \
           getattr(stage1.format, "labelType", None) == "gpt":
            missing = True
            for part in [p for p in storage.partitions if p.disk == stage1]:
                if part.format.type == "biosboot":
                    missing = False
                    break

            if missing:
                exns.append(
                   SanityError(_("Your BIOS-based system needs a special "
                                "partition to boot from a GPT disk label. "
                                "To continue, please create a 1MiB "
                                "'biosboot' type partition.")))

    if not swaps:
        installed = util.total_memory()
        required = Size("%s MiB" % (min_ram + isys.NO_SWAP_EXTRA_RAM))

        if installed < required:
            exns.append(
               SanityError(_("You have not specified a swap partition.  "
                            "%(requiredMem)s of memory is required to continue installation "
                            "without a swap partition, but you only have %(installedMem)s.")
                          % {"requiredMem": required,
                             "installedMem": installed}))
        else:
            exns.append(
               SanityWarning(_("You have not specified a swap partition.  "
                              "Although not strictly required in all cases, "
                              "it will significantly improve performance "
                              "for most installations.")))
    no_uuid = [s for s in swaps if s.format.exists and not s.format.uuid]
    if no_uuid:
        exns.append(
           SanityWarning(_("At least one of your swap devices does not have "
                          "a UUID, which is common in swap space created "
                          "using older versions of mkswap. These devices "
                          "will be referred to by device path in "
                          "/etc/fstab, which is not ideal since device "
                          "paths can change under a variety of "
                          "circumstances. ")))

    for (mountpoint, dev) in filesystems.items():
        if mountpoint in mustbeonroot:
            exns.append(
               SanityError(_("This mount point is invalid.  The %s directory must "
                            "be on the / file system.") % mountpoint))

        if mountpoint in mustbeonlinuxfs and (not dev.format.mountable or not dev.format.linuxNative):
            exns.append(
               SanityError(_("The mount point %s must be on a linux file system.") % mountpoint))

    if storage.rootDevice and storage.rootDevice.format.exists:
        e = storage.mustFormat(storage.rootDevice)
        if e:
            exns.append(SanityError(e))

    exns += verify_LUKS_devices_have_key(storage)

    return exns


def verify_LUKS_devices_have_key(storage):
    """
    Verify that all non-existant LUKS devices have some way of obtaining
    a key.

    Note: LUKS device creation will fail without a key.

    :rtype: generator of str
    :returns: a generator of error messages, may yield no error messages

    """

    for dev in (d for d in storage.devices if \
       d.format.type == "luks" and \
       not d.format.exists and \
       not d.format.hasKey):
        yield LUKSDeviceWithoutKeyError(_("Encryption requested for LUKS device %s but no encryption key specified for this device.") % (dev.name,))


def bound_size(size, device, old_size):
    """ Returns a size bounded by the maximum and minimum size for
        the device.

        :param size: the candidate size
        :type size: :class:`blivet.size.Size`
        :param device: the device being displayed
        :type device: :class:`blivet.devices.StorageDevice`
        :param old_size: the fallback size
        :type old_size: :class:`blivet.size.Size`
        :returns: a size to which to set the device
        :rtype: :class:`blivet.size.Size`

        If size is 0, interpreted as set size to maximum possible.
        If no maximum size is available, reset size to old_size, but
        log a warning.
    """
    max_size = device.maxSize
    min_size = device.minSize
    if not size:
        if max_size:
            log.info("No size specified, using maximum size for this device (%d).", max_size)
            size = max_size
        else:
            log.warning("No size specified and no maximum size available, setting size back to original size (%d).", old_size)
            size = old_size
    else:
        if max_size:
            if size > max_size:
                log.warning("Size specified (%d) is greater than the maximum size for this device (%d), using maximum size.", size, max_size)
                size = max_size
        else:
            log.warning("Unknown upper bound on size. Using requested size (%d).", size)

        if size < min_size:
            log.warning("Size specified (%d) is less than the minimum size for this device (%d), using minimum size.", size, min_size)
            size = min_size

    return size

class StorageSnapshot(object):
    """R/W snapshot of storage (i.e. a :class:`blivet.Blivet` instance)"""

    def __init__(self, storage=None):
        """
        Create new instance of the class

        :param storage: if given, its snapshot is created
        :type storage: :class:`blivet.Blivet`
        """
        if storage:
            self._storage_snap = storage.copy()
        else:
            self._storage_snap = None

    @property
    def storage(self):
        return self._storage_snap

    @property
    def created(self):
        return bool(self._storage_snap)

    def create_snapshot(self, storage):
        """Create (and save) snapshot of storage"""

        self._storage_snap = storage.copy()

    def dispose_snapshot(self):
        """
        Dispose (unref) the snapshot

        .. note::

            In order to free the memory taken by the snapshot, all references
            returned by :property:`self.storage` have to be unrefed too.
        """
        self._storage_snap = None

    def reset_to_snapshot(self, storage, dispose=False):
        """
        Reset storage to snapshot (**modifies :param:`storage` in place**)

        :param storage: :class:`blivet.Blivet` instance to reset to the created snapshot
        :param bool dispose: whether to dispose the snapshot after reset or not
        :raises ValueError: if no snapshot is available (was not created before)
        """
        if not self.created:
            raise ValueError("No snapshot created, cannot reset")

        # we need to create a new copy from the snapshot first -- simple
        # assignment from the snapshot would result in snapshot being modified
        # by further changes of 'storage'
        new_copy = self._storage_snap.copy()
        storage.devicetree = new_copy.devicetree
        storage.roots = new_copy.roots
        storage.fsset = new_copy.fsset

        if dispose:
            self.dispose_snapshot()

# a snapshot of early storage as we got it from scanning disks without doing any
# changes
on_disk_storage = StorageSnapshot()
