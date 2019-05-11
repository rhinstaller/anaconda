#
# Copyright (C) 2019  Red Hat, Inc.
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
import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import arch, util
from blivet.size import Size

from pyanaconda import isys
from pyanaconda.core.constants import STORAGE_MIN_ROOT, productName, STORAGE_REFORMAT_BLACKLIST, \
    STORAGE_REFORMAT_WHITELIST, STORAGE_MIN_PARTITION_SIZES, STORAGE_MIN_RAM, \
    STORAGE_SWAP_IS_RECOMMENDED, STORAGE_MUST_BE_ON_ROOT, STORAGE_MUST_BE_ON_LINUXFS, \
    STORAGE_LUKS2_MIN_RAM
from pyanaconda.core.i18n import _
from pyanaconda.platform import platform as _platform

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


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

    if root and root.format.exists and root.format.mountable and root.format.mountpoint == "/":
        report_error(_("You must create a new file system on the root device."))


def verify_s390_constraints(storage, constraints, report_error, report_warning):
    """ Verify constraints for s390x.

        Prevent users from installing on s390x with (a) no /boot volume, (b) the
        root volume on LVM, (c) the root volume not restricted to a single PV,
        and (d) LDL DASD disks.

        NOTE: There is not really a way for users to create a / volume
        restricted to a single PV.  The backend support is there, but there are
        no UI hook-ups to drive that functionality, but I do not personally
        care.  --dcantrell

        :param storage: a storage to check
        :param constraints: a dictionary of constraints
        :param report_error: a function for error reporting
        :param report_warning: a function for warning reporting
    """
    if not arch.is_s390():
        return

    root = storage.fsset.root_device
    if '/boot' not in storage.mountpoints and root:
        if root.type == 'lvmlv' and not root.single_pv:
            report_error(_("This platform requires /boot on a dedicated "
                           "partition or logical volume. If you do not "
                           "want a /boot volume, you must place / on a "
                           "dedicated non-LVM partition."))

    for disk in storage.disks:
        if disk.type == "dasd" and blockdev.s390.dasd_is_ldl(disk.name):
            report_error(_("The LDL DASD disk {name} ({busid}) cannot be used "
                           "for the installation. Please format it.")
                         .format(name="/dev/" + disk.name, busid=disk.busid))


def verify_partition_formatting(storage, constraints, report_error, report_warning):
    """ Verify partitions that should be reformatted by default.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    mountpoints = [
        mount for mount, device in storage.mountpoints.items()
        if device.format.exists
        and device.format.linux_native
        and not any(filter(mount.startswith, constraints[STORAGE_REFORMAT_BLACKLIST]))
        and any(filter(mount.startswith, constraints[STORAGE_REFORMAT_WHITELIST]))
    ]

    for mount in mountpoints:
        report_warning(_("It is recommended to create a new file system on your "
                         "%(mount)s partition.") % {'mount': mount})


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

        if arch.is_x86() and not arch.is_efi() and stage1 and stage1.is_disk \
                and getattr(stage1.format, "label_type", None) == "gpt":

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
    devices = [d for d in storage.devices
               if d.format.type == "luks"
               and not d.format.exists
               and not d.format.has_key]

    for dev in devices:
        report_error(_("Encryption requested for LUKS device %s but no "
                       "encryption key specified for this device.") % (dev.name,))


def verify_luks2_memory_requirements(storage, constraints, report_error, report_warning):
    """ Verify that there is enough available memory for LUKS2 format.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    devices = [d for d in storage.devices
               if d.format.type == "luks"
               and d.format.luks_version == "luks2"
               and d.format.pbkdf_args is None
               and not d.format.exists]

    available_memory = util.available_memory()
    log.debug("Available memory: %s", available_memory)

    if devices and available_memory < constraints[STORAGE_LUKS2_MIN_RAM]:
        report_warning(_("The available memory is less than %(size)s which can "
                         "be too small for LUKS2 format. It may fail.")
                       % {"size": constraints[STORAGE_LUKS2_MIN_RAM]})


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
            raise KeyError("The constraint {} already exists.".format(name))

        self.constraints[name] = value

    def add_constraint(self, name, value):
        """ Add a constraint for storage checking that will override
        the existing one.

        KeyError will be raised if the constraint does not exist.

        :param str name: a name of the existing constraint
        :param value: a value of the constraint
        """
        if name not in self.constraints:
            raise KeyError("The constraint {} does not exist.".format(name))

        self.constraints[name] = value

    def check(self, storage, constraints=None, skip=None):
        """ Run a series of tests to verify the storage configuration.

        This function is called at the end of partitioning so that we can make
        sure you don't have anything silly (like no /, a really small /, etc).

        :param storage: an instance of the :class:`pyanaconda.storage.InstallerStorage` class to check
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

        self.add_new_constraint(STORAGE_REFORMAT_WHITELIST, {
            '/boot', '/var', '/tmp', '/usr'
        })

        self.add_new_constraint(STORAGE_REFORMAT_BLACKLIST, {
            '/home', '/usr/local', '/opt', '/var/www'
        })

        self.add_new_constraint(STORAGE_SWAP_IS_RECOMMENDED, True)
        self.add_new_constraint(STORAGE_LUKS2_MIN_RAM, Size("128 MiB"))

    def set_default_checks(self):
        """Set the default checks."""
        self.checks = list()
        self.add_check(verify_root)
        self.add_check(verify_s390_constraints)
        self.add_check(verify_partition_formatting)
        self.add_check(verify_partition_sizes)
        self.add_check(verify_partition_format_sizes)
        self.add_check(verify_bootloader)
        self.add_check(verify_gpt_biosboot)
        self.add_check(verify_swap)
        self.add_check(verify_swap_uuid)
        self.add_check(verify_mountpoints_on_linuxfs)
        self.add_check(verify_mountpoints_on_root)
        self.add_check(verify_luks_devices_have_key)
        self.add_check(verify_luks2_memory_requirements)
        self.add_check(verify_mounted_partitions)


# Setup the storage checker.
storage_checker = StorageChecker()
storage_checker.set_default_constraints()
storage_checker.set_default_checks()
