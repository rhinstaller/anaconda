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
import re
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
        report_error(_("A root partition (/) is required for installation. Create one to continue."))

    if root and root.format.exists and root.format.mountable and root.format.mountpoint == "/" \
       and not root.format.is_empty:
        report_error(_("The root partition (/) must be reformatted to continue."))

    if storage.root_device and constraints[STORAGE_ROOT_DEVICE_TYPES]:
        device_type = get_device_type(storage.root_device)
        device_types = constraints[STORAGE_ROOT_DEVICE_TYPES]
        if device_type not in device_types:
            report_error(_("The root partition must be on one of the following device types: %(types)s.")
                         % {"types": ", ".join(DEVICE_TEXT_MAP[t] for t in device_types)})


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
            report_error(_("The LDL DASD disk %(disk)s is unusable. Format it to the CDL layout to continue.")
                         % {"disk": "/dev/" + disk.name})


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
        report_warning(_("To avoid conflicts with existing data, reformat %(mount)s.")
                       % {"mount": mount})


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
            report_warning(_("The %(mount)s partition should be at least %(size)s for a standard installation.")
                           % {"mount": mount, "size": size})

    for (mount, size) in constraints[STORAGE_REQ_PARTITION_SIZES].items():
        if mount in filesystems and filesystems[mount].size < size:
            report_error(_("The %(mount)s partition must be at least %(size)s.")
                         % {"mount": mount, "size": size})


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
            report_error(_("The %(mount)s partition is too small for %(format)s. "
                           "It must be between %(minSize)s and %(maxSize)s.")
                         % {"mount": mount, "format": device.format.name,
                            "minSize": device.min_size, "maxSize": device.max_size})
        elif problem > 0:
            report_error(_("The %(mount)s partition is too large for %(format)s. "
                           "It must be between %(minSize)s and %(maxSize)s.")
                         % {"mount": mount, "format": device.format.name,
                            "minSize": device.min_size, "maxSize": device.max_size})


def verify_bootloader(storage, constraints, report_error, report_warning):
    """ Verify bootloader prerequisites and surface dynamic messages.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    if storage.bootloader and not storage.bootloader.skip_bootloader:
        stage1 = storage.bootloader.stage1_device
        if not stage1:
            report_error(_("A valid target for the boot loader was not found. Create a /boot partition to continue."))
            # Normalize the platform suggestion as a bootloader error for consistent display.
            report_error(_("Boot loader error: %(msg)s") % {"msg": platform.stage1_suggestion})
        else:
            storage.bootloader.is_valid_stage1_device(stage1)
            for msg in storage.bootloader.errors:
                report_error(_("Boot loader error: %(msg)s") % {"msg": msg})

            for msg in storage.bootloader.warnings:
                report_warning(_("Boot loader warning: %(msg)s") % {"msg": msg})

        stage2 = storage.bootloader.stage2_device
        if stage1 and not stage2:
            if arch.is_efi():
                report_error(_("An EFI System Partition (ESP) is required. "
                               "Create a FAT32 partition of at least 100 MiB, set its type to 'EFI System', "
                               "and mount it at /boot/efi."))
            else:
                report_error(_("No partition is marked as \"bootable\". "
                               "Set the boot flag on the appropriate partition (either on / or a /boot partition)."))
        else:
            storage.bootloader.is_valid_stage2_device(stage2)
            for msg in storage.bootloader.errors:
                report_error(_("Boot loader error: %(msg)s") % {"msg": msg})

            for msg in storage.bootloader.warnings:
                report_warning(_("Boot loader warning: %(msg)s") % {"msg": msg})

            if not storage.bootloader.check():
                for msg in storage.bootloader.errors:
                    report_error(_("Boot loader error: %(msg)s") % {"msg": msg})


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
                report_error(_("Booting from a GPT disk on a BIOS system requires a 1 MiB "
                               "'biosboot' type partition on %(disk)s. Create one to continue.")
                             % {"disk": stage1.name})


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
            report_error(_("System firmware does not support booting from an XFS partition. "
                           "Select a different file system type for the boot partition "
                           "or upgrade the firmware to continue."))


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
        required = constraints[STORAGE_MIN_RAM] + Size("%s MiB" % NO_SWAP_EXTRA_RAM)

        # Recommended swap per Red Hat guidelines (no hibernation):
        # <= 2 GiB -> 2x RAM; > 2-8 GiB -> 1x RAM; > 8-64 GiB -> 4 GiB; > 64 GiB -> 4 GiB
        two_gib = Size("2 GiB")
        eight_gib = Size("8 GiB")

        if installed <= two_gib:
            rec_swap = installed * 2
        elif installed <= eight_gib:
            rec_swap = installed
        else:
            rec_swap = Size("4 GiB")

        if not constraints[STORAGE_SWAP_IS_RECOMMENDED]:
            if installed < required:
                report_warning(_("The system has %(installedMem)s of memory, but "
                                 "%(requiredMem)s is recommended. For better performance, "
                                 "create a swap partition of at least %(swapSize)s.")
                               % {"installedMem": installed, "requiredMem": required, "swapSize": rec_swap})
        else:
            if installed < required:
                report_error(_("Insufficient memory to install. %(installedMem)s is available, "
                               "but %(requiredMem)s is required. Create a swap partition of at least %(swapSize)s.")
                             % {"installedMem": installed, "requiredMem": required, "swapSize": rec_swap})
            else:
                report_warning(_("This system only has %(size)s of available memory. "
                                 "Creating a swap partition would dramatically improve system reliability "
                                 "in most scenarios.")
                               % {"size": installed})


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
        report_warning(_("A swap partition is using a device path that can change at boot, "
                         "which might prevent the system from finding it. Recreate the partition "
                         "to assign a stable UUID."))


def verify_mountpoints_on_root(storage, constraints, report_error, report_warning):
    """ Verify mountpoints on the root.

    :param storage: a storage to check
    :param constraints: a dictionary of constraints
    :param report_error: a function for error reporting
    :param report_warning: a function for warning reporting
    """
    for mountpoint in storage.mountpoints:
        if mountpoint in constraints[STORAGE_MUST_BE_ON_ROOT]:
            report_error(_("The %(dir)s directory must be on the root (/) file system, not a separate partition.")
                         % {"dir": mountpoint})


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
            report_error(_("The %(dir)s directory must be on its own separate partition or logical volume.")
                         % {"dir": mountpoint})


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
            report_error(_("The mount point %s must be on a Linux file system.")
                         % mountpoint)


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
        report_error(_("The unlocked LUKS device %(dev)s requires an encryption key. "
                       "Rescan storage and provide its key to continue.") % {"dev": dev.name})


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
        report_error(_("Encryption for %(dev)s requires a passphrase or encryption key. "
                       "Enter one to proceed.") % {"dev": dev.name})


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
        report_warning(_("LUKS2 disk encryption might fail with less than %(size)s of memory. "
                         "Creating a swap partition may help.")
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
            report_error(_("The partition %(path)s is currently in use. "
                           "Unmount the partition to use it for installation.")
                         % {"path": path})


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
            report_error(_("The volume group %(vg)s spans multiple disks, but the current selection "
                           "only includes %(disks)s. Select or deselect all disks in this group to continue.")
                         % {"vg": vg_name, "disks": ", ".join(disks)})


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

    def _join_list(self, items):
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        conj = _("and")
        if len(items) == 2:
            return _("%(a)s %(and)s %(b)s") % {"a": items[0], "and": conj, "b": items[1]}
        head = ", ".join(items[:-1])
        return _("%(head)s, %(and)s %(tail)s") % {"head": head, "and": conj, "tail": items[-1]}

    def _dedupe_preserve_order(self, seq):
        seen = set()
        out = []
        for s in seq:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def _consolidate(self):
        # Warnings: reformat mount(s)
        tpl_reformat = _("To avoid conflicts with existing data, reformat %(mount)s.")
        pat_reformat = re.compile(re.escape(tpl_reformat).replace(re.escape("%(mount)s"), r"(?P<m>.+?)"))

        # Warnings: min recommended size
        tpl_min_size = _("The %(mount)s partition should be at least %(size)s for a standard installation.")
        pat_min_size = re.compile(
            re.escape(tpl_min_size)
            .replace(re.escape("%(mount)s"), r"(.+?)")
            .replace(re.escape("%(size)s"), r"(.+?)")
        )

        # Errors: must be on Linux fs
        tpl_linuxfs = _("The mount point %s must be on a Linux file system.") % "%s"
        pat_linuxfs = re.compile(re.escape(tpl_linuxfs).replace(re.escape("%s"), r"(?P<m>.+?)"))

        # Errors: dir must be on root
        tpl_on_root = _("The %(dir)s directory must be on the root (/) file system, not a separate partition.")
        pat_on_root = re.compile(re.escape(tpl_on_root).replace(re.escape("%(dir)s"), r"(?P<d>.+?)"))

        # Errors: dir must not be on root (own partition/LV)
        tpl_not_on_root = _("The %(dir)s directory must be on its own separate partition or logical volume.")
        pat_not_on_root = re.compile(re.escape(tpl_not_on_root).replace(re.escape("%(dir)s"), r"(?P<d>.+?)"))

        # Errors: partitions currently in use
        tpl_in_use = _("The partition %(path)s is currently in use. "
                       "Unmount the partition to use it for installation.")
        pat_in_use = re.compile(re.escape(tpl_in_use).replace(re.escape("%(path)s"), r"(?P<p>.+?)"))

        # Group warnings
        warn_reformats = []
        warn_min_size_by_size = defaultdict(list)
        remaining_warnings = []

        for w in self.warnings:
            m = pat_reformat.fullmatch(w)
            if m:
                warn_reformats.append(m.group("m"))
                continue
            m = pat_min_size.fullmatch(w)
            if m:
                warn_min_size_by_size[m.group("s")].append(m.group("m"))
                continue
            remaining_warnings.append(w)

        merged_warnings = []

        if warn_reformats:
            merged_warnings.append(
                _("To avoid conflicts with existing data, reformat %(mounts)s.")
                % {"mounts": self._join_list(warn_reformats)}
            )

        for size, mounts in warn_min_size_by_size.items():
            merged_warnings.append(
                _("The following partitions should be at least %(size)s: %(mounts)s.")
                % {"size": size, "mounts": self._join_list(mounts)}
            )

        merged_warnings.extend(remaining_warnings)
        # Final sanitize to guarantee no Pango markup remnants.
        self.warnings = self._dedupe_preserve_order(merged_warnings)

        # Group errors
        err_linuxfs = []
        err_on_root = []
        err_not_on_root = []
        err_in_use = []
        remaining_errors = []

        for e in self.errors:
            m = pat_linuxfs.fullmatch(e)
            if m:
                err_linuxfs.append(m.group("m"))
                continue
            m = pat_on_root.fullmatch(e)
            if m:
                err_on_root.append(m.group("d"))
                continue
            m = pat_not_on_root.fullmatch(e)
            if m:
                err_not_on_root.append(m.group("d"))
                continue
            m = pat_in_use.fullmatch(e)
            if m:
                err_in_use.append(m.group("p"))
                continue
            remaining_errors.append(e)

        merged_errors = []

        if err_linuxfs:
            merged_errors.append(
                _("The following mount points must be on a Linux file system: %(mounts)s.")
                % {"mounts": self._join_list(err_linuxfs)}
            )

        if err_on_root:
            merged_errors.append(
                _("These directories must be on the root (/) file system: %(dirs)s.")
                % {"dirs": self._join_list(err_on_root)}
            )

        if err_not_on_root:
            merged_errors.append(
                _("These directories must be on their own separate partition or logical volume: %(dirs)s.")
                % {"dirs": self._join_list(err_not_on_root)}
            )

        if err_in_use:
            merged_errors.append(
                _("The following partitions are currently in use: %(paths)s. Unmount them to use them for installation.")
                % {"paths": self._join_list(err_in_use)}
            )

        merged_errors.extend(remaining_errors)
        self.errors = self._dedupe_preserve_order(merged_errors)

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

        result._consolidate()

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
