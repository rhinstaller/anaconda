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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from collections import defaultdict

from blivet import arch, blockdev, util
from blivet.devicefactory import get_device_type
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    STORAGE_LUKS2_MIN_RAM,
    STORAGE_MIN_PARTITION_SIZES,
    STORAGE_MIN_RAM,
    STORAGE_MUST_BE_ON_LINUXFS,
    STORAGE_MUST_BE_ON_ROOT,
    STORAGE_MUST_NOT_BE_ON_ROOT,
    STORAGE_REFORMAT_ALLOWLIST,
    STORAGE_REFORMAT_BLOCKLIST,
    STORAGE_REQ_PARTITION_SIZES,
    STORAGE_ROOT_DEVICE_TYPES,
    STORAGE_SWAP_IS_RECOMMENDED,
)
from pyanaconda.core.hw import NO_SWAP_EXTRA_RAM
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import rpm_version_key
from pyanaconda.core.product import get_product_name
from pyanaconda.core.storage import DEVICE_TEXT_MAP
from pyanaconda.modules.storage.platform import platform

log = get_module_logger(__name__)


def verify_root(storage, constraints, report_error, report_warning):
    """ Verify the root.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    root = storage.fsset.root_device

    if not root:
        report_error(_("You have not defined a root partition (/), "
                       "which is required for installation of %(prod_name)s "
                       "to continue.") % {"prod_name": get_product_name()})

    if root and root.format.exists and root.format.mountable and root.format.mountpoint == "/" \
       and not root.format.is_empty:
        report_error(_("You must create a new file system on the root device."))

    if storage.root_device and constraints[STORAGE_ROOT_DEVICE_TYPES]:
        device_type = get_device_type(storage.root_device)
        device_types = constraints[STORAGE_ROOT_DEVICE_TYPES]
        if device_type not in device_types:
            report_error(_("Your root partition must be on a device of type: %s.")
                         % ", ".join(DEVICE_TEXT_MAP[t] for t in device_types))


def verify_s390_constraints(storage, constraints, report_error, report_warning):
    """ Verify constraints for s390x.

        Prevent users from installing on s390x with LDL DASD disks.

        :param storage: a storage to check
        :param constraints: a dictionary of constraints
        :param report_error: a function for error reporting
        :param report_warning: a function for warning reporting
    """
    if not arch.is_s390():
        return

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
        and not any(filter(mount.startswith, constraints[STORAGE_REFORMAT_BLOCKLIST]))
        and any(filter(mount.startswith, constraints[STORAGE_REFORMAT_ALLOWLIST]))
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
                              'productName': get_product_name()})

    for (mount, size) in constraints[STORAGE_REQ_PARTITION_SIZES].items():
        if mount in filesystems and filesystems[mount].size < size:
            report_error(_("Your %(mount)s partition size is lower "
                           "than required %(size)s.")
                         % {'mount': mount, 'size': size})


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
        problem = device.check_size()
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
            report_error(platform.stage1_suggestion)
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
    if not storage.bootloader or storage.bootloader.skip_bootloader:
        return

    for stage1, _stage2 in storage.bootloader.install_targets:
        if arch.is_x86() and not arch.is_efi() and stage1 and stage1.is_disk \
                and getattr(stage1.format, "label_type", None) == "gpt":

            missing = True
            for part in [p for p in storage.partitions if p.disk == stage1]:
                if part.format.type == "biosboot":
                    missing = False
                    break

            if missing:
                report_error(_(
                    "Your BIOS-based system needs a special "
                    "partition to boot from a GPT disk label. "
                    "To continue, please create a 1MiB "
                    "'biosboot' type partition on the {} disk."
                ).format(stage1.name))


def verify_opal_compatibility(storage, constraints, report_error, report_warning):
    """ Verify the OPAL compatibility.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    if arch.get_arch() == "ppc64le" and arch.is_powernv():
        # Check the kernel version.
        version = _get_opal_firmware_kernel_version()
        if _check_opal_firmware_kernel_version(version, "5.10"):
            return

        # Is /boot on XFS?
        dev = storage.mountpoints.get("/boot") or storage.mountpoints.get("/")
        if dev and dev.format and dev.format.type == "xfs":
            report_error(_(
                "The system will not be bootable. The firmware does not "
                "support XFS file system features on the boot file system. "
                "Upgrade the firmware or change the file system type."
            ))


def _check_opal_firmware_kernel_version(detected_version, required_version):
    """Check the firmware kernel version for OPAL systems.

    :param detected_version: a string with the detected kernel version or None
    :param required_version: a string with the required kernel version or None
    :return: True or False
    """
    try:
        if detected_version and required_version:
            return rpm_version_key(detected_version) >= rpm_version_key(required_version)
    except Exception as e:  # pylint: disable=broad-except
        log.warning("Couldn't check the firmware kernel version: %s", str(e))

    return False


def _get_opal_firmware_kernel_version():
    """Get the firmware kernel version for OPAL systems.

    For example: 5.10.50-openpower1-p59fd803

    :return: a string with the kernel version or None
    """
    version = None

    try:
        with open("/proc/device-tree/ibm,firmware-versions/linux") as f:
            version = f.read().strip().removeprefix("v")
            log.debug("The firmware kernel version is '%s'.", version)

    except IOError as e:
        log.warning("Couldn't get the firmware kernel version: %s", str(e))

    return version


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
        required = constraints[STORAGE_MIN_RAM] + Size("{} MiB".format(NO_SWAP_EXTRA_RAM))

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
                report_warning(_(
                    "A swap partition has not been specified. To significantly "
                    "improve performance for most installations, it is recommended "
                    "to specify a swap partition."
                ))


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
                         "circumstances."))


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


def verify_mountpoints_not_on_root(storage, constraints, report_error, report_warning):
    """ Verify mountpoints not on the root.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    filesystems = storage.mountpoints

    for mountpoint in constraints[STORAGE_MUST_NOT_BE_ON_ROOT]:
        if mountpoint not in filesystems:
            report_error(_("Your %s must be on a separate partition or LV.")
                         % mountpoint)


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


def verify_unlocked_devices_have_key(storage, constraints, report_error, report_warning):
    """ Verify that existing unlocked LUKS devices have some way of obtaining a key.

    Blivet doesn't remove decrypted devices after a teardown of unlocked LUKS devices
    and later fails to set them up without a key, so report an error to prevent a
    traceback during the installation.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    devices = [
        d for d in storage.devices
        if d.format.type == "luks"
        and d.format.exists
        and not d.format.has_key
        and d.children
    ]

    for dev in devices:
        report_error(_("The existing unlocked LUKS device {} cannot be used for "
                       "the installation without an encryption key specified for "
                       "this device. Please, rescan the storage.").format(dev.name))


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

    Check both the currently known and original partitions.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    partitions_to_check = {}

    for disk in storage.disks:
        if disk.protected:
            continue

        if not disk.partitioned:
            continue

        for part in disk.format.partitions:
            if part.path not in partitions_to_check:
                partitions_to_check[part.path] = part

        if hasattr(disk.original_format, "partitions"):
            for part in disk.original_format.partitions:
                if part.path not in partitions_to_check:
                    partitions_to_check[part.path] = part

    for path, part in partitions_to_check.items():
        part_dev = storage.devicetree.get_device_by_path(path)
        if part_dev and part_dev.protected:
            log.debug("Not checking protected %s for being mounted, assuming live "
                      "image mount", path)
            return

        if part.busy:
            report_error(_("%s is currently mounted and cannot be used for the "
                           "installation. Please unmount it and retry.") % path)


def verify_lvm_destruction(storage, constraints, report_error, report_warning):
    """Verify that destruction of LVM devices is correct.

    A VG and all its PVs must be all destroyed together, nothing is allowed to remain.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    # Implementation detects VGs that should be destroyed and aren't. This is because of how
    # blivet implements ignoring devices: Ignoring a device hides also all dependent devices - for
    # any disk, it could be a PV partition, which would then hide also all VGs and LVs that depend
    # on the PV. It does not matter that the VG needs other PVs too - the hiding wins.
    destroyed_vg_names = set()
    all_touched_disks_by_vg = defaultdict(list)

    for action in storage.devicetree.actions:
        if action.is_destroy and action.is_device and action.device.type == "lvmvg":
            destroyed_vg_names.add(action.device.name)

        elif action.is_destroy and action.is_format and action.orig_format.type == "lvmpv":
            # Check if the PV actually had any VG assigned
            if action.orig_format.vg_name:
                disk_name = action.device.disk.name
                vg_name = action.orig_format.vg_name
                all_touched_disks_by_vg[vg_name].append(disk_name)

    for vg_name, disks in all_touched_disks_by_vg.items():
        if vg_name not in destroyed_vg_names:
            report_error(_(
                "Selected disks {disks} contain volume group '{vg}' that also uses further "
                "unselected disks. You must select or de-select all these disks as a set.")
                .format(disks=", ".join(disks), vg=vg_name)
            )


class StorageCheckerReport:
    """Class for results of the storage checking."""

    def __init__(self):
        self.info = []
        self.errors = []
        self.warnings = []

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


class StorageChecker:
    """Class for advanced storage checking."""

    def __init__(self):
        self.checks = []
        self.constraints = {}

    def add_check(self, callback):
        """ Add a callback for storage checking.

        :param callback: a check for the storage checking
        :type callback: a function with arguments (storage, constraints,
        report_error, report_warning), where storage is an instance of the
        storage to check, constraints is a dictionary of constraints and
        report_error and report_warning are functions for reporting messages.
        """
        self.checks.append(callback)

    def add_constraint(self, name, value):
        """ Add a new constraint for storage checking.

        KeyError will be raised if the constraint already exists.

        :param str name: a name of the new constraint
        :param value: a value of the constraint
        """
        if name in self.constraints:
            raise KeyError("The constraint {} already exists.".format(name))

        self.constraints[name] = value

    def set_constraint(self, name, value):
        """ Set an existing constraint to a new value.

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

        :param storage: the storage object to check
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

    def get_default_constraint_names(self):
        """Get a list of default constraint names."""
        return [
            STORAGE_MIN_RAM,
            STORAGE_ROOT_DEVICE_TYPES,
            STORAGE_MIN_PARTITION_SIZES,
            STORAGE_REQ_PARTITION_SIZES,
            STORAGE_MUST_BE_ON_LINUXFS,
            STORAGE_MUST_BE_ON_ROOT,
            STORAGE_MUST_NOT_BE_ON_ROOT,
            STORAGE_REFORMAT_ALLOWLIST,
            STORAGE_REFORMAT_BLOCKLIST,
            STORAGE_SWAP_IS_RECOMMENDED,
            STORAGE_LUKS2_MIN_RAM,
        ]

    def set_default_constraints(self):
        """Set the default constraints needed by default checks."""
        self.constraints = {}

        for name in self.get_default_constraint_names():
            self.add_constraint(name, getattr(conf.storage_constraints, name))

    def set_default_checks(self):
        """Set the default checks."""
        self.checks = []
        self.add_check(verify_root)
        self.add_check(verify_s390_constraints)
        self.add_check(verify_partition_formatting)
        self.add_check(verify_partition_sizes)
        self.add_check(verify_partition_format_sizes)
        self.add_check(verify_bootloader)
        self.add_check(verify_gpt_biosboot)
        self.add_check(verify_opal_compatibility)
        self.add_check(verify_swap)
        self.add_check(verify_swap_uuid)
        self.add_check(verify_mountpoints_on_linuxfs)
        self.add_check(verify_mountpoints_on_root)
        self.add_check(verify_mountpoints_not_on_root)
        self.add_check(verify_unlocked_devices_have_key)
        self.add_check(verify_luks_devices_have_key)
        self.add_check(verify_luks2_memory_requirements)
        self.add_check(verify_mounted_partitions)
        self.add_check(verify_lvm_destruction)


# Setup the storage checker.
storage_checker = StorageChecker()
storage_checker.set_default_constraints()
storage_checker.set_default_checks()
