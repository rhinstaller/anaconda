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

"""UI-independent storage utility functions"""

import re
import locale
import os

from contextlib import contextmanager

from blivet import arch
from blivet import util
from blivet import udev
from blivet.size import Size
from blivet.errors import StorageError
from blivet.formats import device_formats
from blivet.formats.fs import FS
from blivet.platform import platform as _platform
from blivet.autopart import swap_suggestion
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_DISK

from pyanaconda.i18n import _, N_
from pyanaconda import isys
from pyanaconda.constants import productName, STORAGE_SWAP_IS_RECOMMENDED, STORAGE_MUST_BE_ON_ROOT, \
    STORAGE_MUST_BE_ON_LINUXFS, STORAGE_MIN_PARTITION_SIZES, STORAGE_MIN_ROOT, STORAGE_MIN_RAM
from pyanaconda.errors import errorHandler, ERROR_RAISE

from pykickstart.constants import AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS
from pykickstart.constants import AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

import logging

from pyanaconda.anaconda_loggers import get_module_logger, get_blivet_logger
log = get_module_logger(__name__)

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
                                           "boot loader configuration on some PPC platforms.")}

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

udev_device_dict_cache = None

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

    storage_log = get_blivet_logger()
    storage_filter = UIStorageFilter()
    storage_log.addFilter(storage_filter)
    yield
    storage_log.removeFilter(storage_filter)


def verify_root(storage, constraints, report_error, report_warning):
    """ Verify the root.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    root = storage.fsset.root_device

    if root:
        if root.size < constraints[STORAGE_MIN_ROOT]:
            report_warning(_("Your root partition is less than %(size)s "
                             "which is usually too small to install "
                             "%(product)s.")
                           % {'size': constraints[STORAGE_MIN_ROOT],
                              'product': productName})
    else:
        report_error(_("You have not defined a root partition (/), "
                       "which is required for installation of %s"
                       " to continue.") % (productName,))

    if storage.root_device and storage.root_device.format.exists:
        e = storage.must_format(storage.root_device)
        if e:
            report_error(e)


def verify_s390_constraints(storage, constraints, report_error, report_warning):
    """ Verify constraints for s390x.

        Prevent users from installing on s390x with (a) no /boot volume, (b) the
        root volume on LVM, and (c) the root volume not restricted to a single
        PV

        NOTE: There is not really a way for users to create a / volume
        restricted to a single PV.  The backend support is there, but there are
        no UI hook-ups to drive that functionality, but I do not personally
        care.  --dcantrell

        :param storage: a storage to check
        :param constraints: a dictionary of constraints
        :param report_error: a function for error reporting
        :param report_warning: a function for warning reporting
    """
    root = storage.fsset.root_device

    if arch.is_s390() and '/boot' not in storage.mountpoints and root:
        if root.type == 'lvmlv' and not root.single_pv:
            report_error(_("This platform requires /boot on a dedicated "
                           "partition or logical volume. If you do not "
                           "want a /boot volume, you must place / on a "
                           "dedicated non-LVM partition."))


def verify_partition_sizes(storage, constraints, report_error, report_warning):
    """ Verify the minimal and required partition sizes.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    filesystems = storage.mountpoints

    for (mount, size) in constraints[STORAGE_MIN_PARTITION_SIZES].items():
        if mount in filesystems and filesystems[mount].size < size:
            report_warning(_("Your %(mount)s partition is less than "
                             "%(size)s which is lower than recommended "
                             "for a normal %(productName)s install.")
                           % {'mount': mount, 'size': size,
                              'productName': productName})


def verify_partition_format_sizes(storage, constraints, report_error, report_warning):
    """ Verify that the size of the device is allowed by the format used.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    # storage.mountpoints is a property that returns a new dict each time, so
    # iterating over it is thread-safe.
    filesystems = storage.mountpoints

    for (mount, device) in filesystems.items():
        problem = filesystems[mount].check_size()
        if problem < 0:
            report_error(_("Your %(mount)s partition is too small for "
                           "%(format)s formatting (allowable size is "
                           "%(minSize)s to %(maxSize)s)")
                         % {"mount": mount, "format": device.format.name,
                            "minSize": device.min_size, "maxSize": device.max_size})
        elif problem > 0:
            report_error(_("Your %(mount)s partition is too large for "
                           "%(format)s formatting (allowable size is "
                           "%(minSize)s to %(maxSize)s)")
                         % {"mount": mount, "format": device.format.name,
                            "minSize": device.min_size, "maxSize": device.max_size})


def verify_bootloader(storage, constraints, report_error, report_warning):
    """ Verify that the size of the device is allowed by the format used.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    if storage.bootloader and not storage.bootloader.skip_bootloader:
        stage1 = storage.bootloader.stage1_device
        if not stage1:
            report_error(_("No valid boot loader target device found. "
                           "See below for details."))
            pe = _platform.stage1_missing_error
            if pe:
                report_error(_(pe))
        else:
            storage.bootloader.is_valid_stage1_device(stage1)
            for msg in storage.bootloader.errors:
                report_error(msg)

            for msg in storage.bootloader.warnings:
                report_warning(msg)

        stage2 = storage.bootloader.stage2_device
        if stage1 and not stage2:
            report_error(_("You have not created a bootable partition."))
        else:
            storage.bootloader.is_valid_stage2_device(stage2)
            for msg in storage.bootloader.errors:
                report_error(msg)

            for msg in storage.bootloader.warnings:
                report_warning(msg)

            if not storage.bootloader.check():
                for msg in storage.bootloader.errors:
                    report_error(msg)


def verify_gpt_biosboot(storage, constraints, report_error, report_warning):
    """ Verify that GPT boot disk on BIOS system has a BIOS boot partition.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    if storage.bootloader and not storage.bootloader.skip_bootloader:
        stage1 = storage.bootloader.stage1_device

        if _platform.weight(fstype="biosboot") and stage1 and stage1.is_disk \
                and getattr(stage1.format, "labelType", None) == "gpt":

            missing = True
            for part in [p for p in storage.partitions if p.disk == stage1]:
                if part.format.type == "biosboot":
                    missing = False
                    break

            if missing:
                report_error(_("Your BIOS-based system needs a special "
                               "partition to boot from a GPT disk label. "
                               "To continue, please create a 1MiB "
                               "'biosboot' type partition."))


def verify_swap(storage, constraints, report_error, report_warning):
    """ Verify the existence of swap.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    swaps = storage.fsset.swap_devices

    if not swaps:
        installed = util.total_memory()
        required = Size("%s MiB" % (constraints[STORAGE_MIN_RAM] + isys.NO_SWAP_EXTRA_RAM))

        if not constraints[STORAGE_SWAP_IS_RECOMMENDED]:
            if installed < required:
                report_warning(_("You have not specified a swap partition. "
                                 "%(requiredMem)s of memory is recommended to continue "
                                 "installation without a swap partition, but you only "
                                 "have %(installedMem)s.")
                               % {"requiredMem": required, "installedMem": installed})
        else:
            if installed < required:
                report_error(_("You have not specified a swap partition. "
                               "%(requiredMem)s of memory is required to continue "
                               "installation without a swap partition, but you only "
                               "have %(installedMem)s.")
                             % {"requiredMem": required, "installedMem": installed})
            else:
                report_warning(_("You have not specified a swap partition. "
                                 "Although not strictly required in all cases, "
                                 "it will significantly improve performance "
                                 "for most installations."))

    else:
        swap_space = sum((device.size for device in swaps), Size(0))
        disk_space = sum((device.size for device in storage.mountpoints.values()), Size(0))
        recommended = swap_suggestion(disk_space=disk_space, quiet=True)

        log.debug("Total swap space: %s", swap_space)
        log.debug("Used disk space: %s", disk_space)
        log.debug("Recommended swaps space: %s", recommended)

        if swap_space < recommended:
            report_warning(_("Your swap space is less than %(size)s "
                             "which is lower than recommended.")
                           % {"size": recommended})


def verify_swap_uuid(storage, constraints, report_error, report_warning):
    """ Verify swap uuid.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    swaps = storage.fsset.swap_devices
    no_uuid = [s for s in swaps if s.format.exists and not s.format.uuid]

    if no_uuid:
        report_warning(_("At least one of your swap devices does not have "
                         "a UUID, which is common in swap space created "
                         "using older versions of mkswap. These devices "
                         "will be referred to by device path in "
                         "/etc/fstab, which is not ideal since device "
                         "paths can change under a variety of "
                         "circumstances. "))


def verify_mountpoints_on_root(storage, constraints, report_error, report_warning):
    """ Verify mountpoints on the root.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    for mountpoint in storage.mountpoints:
        if mountpoint in constraints[STORAGE_MUST_BE_ON_ROOT]:
            report_error(_("This mount point is invalid. The %s directory must "
                           "be on the / file system.") % mountpoint)


def verify_mountpoints_on_linuxfs(storage, constraints, report_error, report_warning):
    """ Verify mountpoints on linuxfs.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    filesystems = storage.mountpoints

    for (mountpoint, dev) in filesystems.items():
        if mountpoint in constraints[STORAGE_MUST_BE_ON_LINUXFS] \
                and (not dev.format.mountable or not dev.format.linux_native):
            report_error(_("The mount point %s must be on a linux file system.") % mountpoint)


def verify_luks_devices_have_key(storage, constraints, report_error, report_warning):
    """ Verify that all non-existant LUKS devices have some way of obtaining a key.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting

    Note: LUKS device creation will fail without a key.
    """
    devices = (d for d in storage.devices
               if d.format.type == "luks"
               and not d.format.exists
               and not d.format.has_key)

    for dev in devices:
        report_error(_("Encryption requested for LUKS device %s but no "
                       "encryption key specified for this device.") % (dev.name,))


def verify_mounted_partitions(storage, constraints, report_error, report_warning):
    """ Check the selected disks to make sure all their partitions are unmounted.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    for disk in storage.disks:
        if not disk.partitioned:
            continue

        for part in disk.format.partitions:
            part_dev = storage.devicetree.get_device_by_path(part.path)
            if part_dev and part_dev.protected:
                log.debug("Not checking protected %s for being mounted, assuming live "
                          "image mount", part.path)
                continue
            if part.busy:
                report_error(_("%s is currently mounted and cannot be used for the "
                               "installation. Please unmount it and retry.") % part.path)


class StorageCheckerReport(object):
    """Class for results of the storage checking."""

    def __init__(self):
        self.info = list()
        self.errors = list()
        self.warnings = list()

    @property
    def all_errors(self):
        """Return a list of errors and warnings."""
        return self.errors + self.warnings

    @property
    def success(self):
        """Success, if no errors and warnings were reported."""
        return not self.failure

    @property
    def failure(self):
        """Failure, if some errors or warnings were reported."""
        return bool(self.errors or self.warnings)

    def add_info(self, msg):
        """ Add an error message.

        :param str msg: an info message
        """
        self.info.append(msg)

    def add_error(self, msg):
        """ Add an error message.

        :param str msg: an error message
        """
        self.add_info("Found sanity error: %s" % msg)
        self.errors.append(msg)

    def add_warning(self, msg):
        """ Add a warning message.

        :param str msg: a warning message
        """
        self.add_info("Found sanity warning: %s" % msg)
        self.warnings.append(msg)

    def log(self, logger, error=True, warning=True, info=True):
        """ Log the messages.

        :param logger: an instance of logging.Logger
        :param bool error: should we log the error messages?
        :param bool warning: should we log the warning messages?
        :param bool info: should we log the info messages?
        """
        if info:
            for msg in self.info:
                logger.debug(msg)

        if error:
            for msg in self.errors:
                logger.error(msg)

        if warning:
            for msg in self.warnings:
                logger.warning(msg)


class StorageChecker(object):
    """Class for advanced storage checking."""

    def __init__(self):
        self.checks = list()
        self.constraints = dict()

    def add_check(self, callback):
        """ Add a callback for storage checking.

        :param callback: a check for the storage checking
        :type callback: a function with arguments (storage, constraints,
        report_error, report_warning), where storage is an instance of the
        storage to check, constraints is a dictionary of constraints and
        report_error and report_warning are functions for reporting messages.
        """
        self.checks.append(callback)

    def remove_check(self, callback):
        """ Remove a callback for storage checking.

        :param callback: a check for the storage checking
        """
        if callback in self.checks:
            self.checks.remove(callback)

    def add_new_constraint(self, name, value):
        """ Add a new constraint for storage checking.

        KeyError will be raised if the constraint already exists.

        :param str name: a name of the new constraint
        :param value: a value of the constraint
        """
        if name in self.constraints:
            raise KeyError("The constraint %s already exists.", name)

        self.constraints[name] = value

    def add_constraint(self, name, value):
        """ Add a constraint for storage checking that will override
        the existing one.

        KeyError will be raised if the constraint does not exist.

        :param str name: a name of the existing constraint
        :param value: a value of the constraint
        """
        if name not in self.constraints:
            raise KeyError("The constraint %s does not exist.", name)

        self.constraints[name] = value

    def update_constraint(self, name, value):
        """ Update a constraint for storage checking if the
        constraint is a dictionary or a set.

        AttributeError will be raised, if the constraint
        does not have the update method.

        KeyError will be raised, if the constraint does
        not exists.

        :param str name: a name of the constraint
        :param value: a value of the constraint (set or dictionary)
        """
        self.constraints[name].update(value)

    def check(self, storage, constraints=None, skip=None):
        """ Run a series of tests to verify the storage configuration.

        This function is called at the end of partitioning so that we can make
        sure you don't have anything silly (like no /, a really small /, etc).

        :param storage: an instance of the :class:`blivet.Blivet` class to check
        :param constraints: an dictionary of constraints that will be used by
               checks or None if we want to use the storage checker's constraints
        :param skip: a collection of checks we want to skip or None if we don't
               want to skip any
        :return an instance of StorageCheckerReport with reported errors and warnings
        """
        if constraints is None:
            constraints = self.constraints

        # Report the constraints.
        result = StorageCheckerReport()
        result.add_info("Storage check started with constraints %s."
                        % constraints)

        # Process checks.
        for check in self.checks:
            # Skip this check.
            if skip and check in skip:
                result.add_info("Skipped sanity check %s." % check.__name__)
                continue

            # Run the check.
            result.add_info("Run sanity check %s." % check.__name__)
            check(storage, constraints, result.add_error, result.add_warning)

        # Report the result.
        if result.success:
            result.add_info("Storage check finished with success.")
        else:
            result.add_info("Storage check finished with failure(s).")

        return result

    def set_default_constraints(self):
        """Set the default constraints needed by default checks."""
        self.constraints = dict()
        self.add_new_constraint(STORAGE_MIN_RAM, isys.MIN_RAM)
        self.add_new_constraint(STORAGE_MIN_ROOT, Size("250 MiB"))
        self.add_new_constraint(STORAGE_MIN_PARTITION_SIZES, {
            '/usr': Size("250 MiB"),
            '/tmp': Size("50 MiB"),
            '/var': Size("384 MiB"),
            '/home': Size("100 MiB"),
            '/boot': Size("200 MiB")
        })

        self.add_new_constraint(STORAGE_MUST_BE_ON_LINUXFS, {
            '/', '/var', '/tmp', '/usr', '/home', '/usr/share', '/usr/lib'
        })

        self.add_new_constraint(STORAGE_MUST_BE_ON_ROOT, {
            '/bin', '/dev', '/sbin', '/etc', '/lib', '/root', '/mnt', 'lost+found', '/proc'
        })

        self.add_new_constraint(STORAGE_SWAP_IS_RECOMMENDED, True)

    def set_default_checks(self):
        """Set the default checks."""
        self.checks = list()
        self.add_check(verify_root)
        self.add_check(verify_s390_constraints)
        self.add_check(verify_partition_sizes)
        self.add_check(verify_partition_format_sizes)
        self.add_check(verify_bootloader)
        self.add_check(verify_gpt_biosboot)
        self.add_check(verify_swap)
        self.add_check(verify_swap_uuid)
        self.add_check(verify_mountpoints_on_linuxfs)
        self.add_check(verify_mountpoints_on_root)
        self.add_check(verify_luks_devices_have_key)
        self.add_check(verify_mounted_partitions)


# Setup the storage checker.
storage_checker = StorageChecker()
storage_checker.set_default_constraints()
storage_checker.set_default_checks()


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
    max_size = device.max_size
    min_size = device.min_size
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

def try_populate_devicetree(devicetree):
    """
    Try to populate the given devicetree while catching errors and dealing with
    some special ones in a nice way (giving user chance to do something about
    them).

    :param devicetree: devicetree to try to populate
    :type decicetree: :class:`blivet.devicetree.DeviceTree`

    """

    while True:
        try:
            devicetree.populate()
        except StorageError as e:
            if errorHandler.cb(e) == ERROR_RAISE:
                raise
            else:
                continue
        else:
            break

    return

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

def filter_unsupported_disklabel_devices(devices):
    """ Return input list minus any devices that exist on an unsupported disklabel. """
    return [d for d in devices
            if not any(not getattr(p, "disklabel_supported", True) for p in d.ancestors)]

def device_name_is_disk(device_name, devicetree=None, refresh_udev_cache=False):
    """Report if the given device name corresponds to a disk device.

    Check if the device name is a disk device or not. This function uses
    the provided Blivet devicetree for the checking and Blivet udev module
    if no devicetree is provided.

    Please note that the udev based check uses an internal cache that is generated
    when this function is first called in the udev checking mode. This basically
    means that udev devices added later will not be taken into account.
    If this is a problem for your usecase then use the refresh_udev_cache option
    to force a refresh of the udev cache.

    :param str device_name: name of the device to check
    :param devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool refresh_udev_cache: governs if the udev device cache should be refreshed
    :returns: True if the device name corresponds to a disk, False if not
    :rtype: bool
    """
    if devicetree is None:
        global udev_device_dict_cache
        if device_name:
            if udev_device_dict_cache is None or refresh_udev_cache:
                # Lazy load the udev dick that contains the {device_name : udev_device,..,}
                # mappings. The operation could be quite costly due to udev_settle() calls,
                # so we cache it in this non-elegant way.
                # An unfortunate side effect of this is that udev devices that show up after
                # this function is called for the first time will not be taken into account.
                udev_device_dict_cache = {udev.device_get_name(d): d for d in udev.get_devices()}
            udev_device = udev_device_dict_cache.get(device_name)
            return udev_device and udev.device_is_realdisk(udev_device)
        else:
            return False
    else:
        device = devicetree.get_device_by_name(device_name)
        return device and device.is_disk

def device_matches(spec, devicetree=None, disks_only=False):
    """Return names of block devices matching the provided specification.

    :param str spec: a device identifier (name, UUID=<uuid>, &c)
    :keyword devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool disks_only: if only disk devices matching the spec should be returned
    :returns: names of matching devices
    :rtype: list of str

    The spec can contain multiple "sub specs" delimited by a |, for example:

    "sd*|hd*|vd*"

    In such case we resolve the specs from left to right and return all
    unique matches, for example:

    ["sda", "sda1", "sda2", "sdb", "sdb1", "vdb"]

    If disks_only is specified we only return
    disk devices matching the spec. For the example above
    the output with disks_only=True would be:

    ["sda", "sdb", "vdb"]

    Also note that parse methods will not have access to a devicetree, while execute
    methods will. The devicetree is superior in that it can resolve md
    array names and in that it reflects scheduled device removals, but for
    normal local disks udev.resolve_devspec should suffice.
    """

    matches = []
    # the device specifications might contain multiple "sub specs" separated by a |
    # - the specs are processed from left to right
    for single_spec in spec.split("|"):
        full_spec = single_spec
        if not full_spec.startswith("/dev/"):
            full_spec = os.path.normpath("/dev/" + full_spec)

        # the regular case
        single_spec_matches = udev.resolve_glob(full_spec)
        for match in single_spec_matches:
            if match not in matches:
                # skip non-disk devices in disk-only mode
                if disks_only and not device_name_is_disk(match):
                    continue
                matches.append(match)

        dev_name = None
        # Use spec here instead of full_spec to preserve the spec and let the
        # called code decide whether to treat the spec as a path instead of a name.
        if devicetree is None:
            # we run the spec through resolve_devspec() here as unlike resolve_glob()
            # it can also resolve labels and UUIDs
            dev_name = udev.resolve_devspec(single_spec)
            if disks_only and dev_name:
                if not device_name_is_disk(dev_name):
                    dev_name = None  # not a disk
        else:
            # devicetree can also handle labels and UUIDs
            device = devicetree.resolve_device(single_spec)
            if device:
                dev_name = device.name
                if disks_only and not device_name_is_disk(dev_name, devicetree=devicetree):
                    dev_name = None  # not a disk

        # The dev_name variable can be None if the spec is not not found or is not valid,
        # but we don't want that ending up in the list.
        if dev_name and dev_name not in matches:
            matches.append(dev_name)

    return matches

def get_supported_filesystems():
    fs_types = []
    for cls in device_formats.values():
        obj = cls()

        # btrfs is always handled by on_device_type_changed
        supported_fs = (obj.supported and obj.formattable and
                        (isinstance(obj, FS) or
                         obj.type in ["biosboot", "prepboot", "swap"]))
        if supported_fs:
            fs_types.append(obj)

    return fs_types
