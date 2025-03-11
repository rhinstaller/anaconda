#
# Copyright (C) 2019 Red Hat, Inc.
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
import blivet.arch
from blivet.devices import iScsiDiskDevice

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    BOOTLOADER_ENABLED,
    BOOTLOADER_LOCATION_PARTITION,
    BOOTLOADER_SKIPPED,
)
from pyanaconda.core.i18n import _
from pyanaconda.core.storage import device_matches
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.bootloader.base import (
    BootLoaderError,
    is_on_non_ibft_sw_iscsi,
)

log = get_module_logger(__name__)

__all__ = ["setup_bootloader"]


def setup_bootloader(storage, dry_run=False):
    """Resolve and setup the bootloader configuration.

    :param Blivet storage: an instance of the storage
    :param bool dry_run: don't set devices if True
    """
    executor = BootloaderExecutor()
    executor.execute(storage=storage, dry_run=dry_run)


class BootloaderExecutor:
    """The executor of the bootloader command."""

    def execute(self, storage, dry_run=False):
        """Execute the bootloader."""
        log.debug("Execute the bootloader with dry run %s.", dry_run)
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

        # Skip bootloader for s390x image installation.
        if blivet.arch.is_s390() \
                and conf.target.is_image \
                and bootloader_proxy.BootloaderMode == BOOTLOADER_ENABLED:
            bootloader_proxy.BootloaderMode = BOOTLOADER_SKIPPED

        # Is the bootloader enabled?
        if bootloader_proxy.BootloaderMode != BOOTLOADER_ENABLED:
            storage.bootloader.skip_bootloader = True
            log.debug("Bootloader is not enabled, skipping.")
            return

        # Update the disk list. Disks are already sorted by Blivet.
        storage.bootloader.set_disk_list([d for d in storage.disks if d.partitioned])

        # Apply settings related to boot devices.
        self._apply_location(storage, bootloader_proxy)
        self._apply_drive_order(storage, bootloader_proxy, dry_run=dry_run)
        self._apply_boot_drive(storage, bootloader_proxy, dry_run=dry_run)

        # Set the stage2 and stage1 devices.
        if not dry_run:
            storage.bootloader.stage2_device = storage.boot_device
            storage.bootloader.set_stage1_device(storage.devices)

    def _apply_location(self, storage, bootloader_proxy):
        """Set the location."""
        location = bootloader_proxy.PreferredLocation
        log.debug("Applying bootloader location: %s", location)

        storage.bootloader.set_preferred_stage1_type(
            "boot" if location == BOOTLOADER_LOCATION_PARTITION else "mbr"
        )

    def _is_usable_disk(self, d):
        """Is the disk usable for the bootloader?

        Throw out drives that don't exist or cannot be used
        (iSCSI device on an s390 machine).
        """
        return \
            not d.format.hidden and \
            not d.protected and \
            not (blivet.arch.is_s390() and isinstance(d, iScsiDiskDevice)) and \
            (not is_on_non_ibft_sw_iscsi(d) or conf.bootloader.nonibft_iscsi_boot)

    def _get_usable_disks(self, storage):
        """Get a list of usable disks."""
        return [d.name for d in storage.disks if self._is_usable_disk(d)]

    def _apply_drive_order(self, storage, bootloader_proxy, dry_run=False):
        """Apply the drive order.

        Drive specifications can contain | delimited variant specifications,
        such as for example: "vd*|hd*|sd*"

        So use the resolved disk identifiers returned by the device_matches()
        function in place of the original specification but still remove the
        specifications that don't match anything from the output kickstart to
        keep existing --driveorder processing behavior.
        """
        drive_order = bootloader_proxy.DriveOrder
        usable_disks = set(self._get_usable_disks(storage))
        valid_disks = []

        for drive in drive_order[:]:
            # Resolve disk identifiers.
            matched_disks = device_matches(drive, devicetree=storage.devicetree, disks_only=True)

            # Are any of the matched disks usable?
            if any(d in usable_disks for d in matched_disks):
                valid_disks.extend(matched_disks)
            else:
                drive_order.remove(drive)
                log.warning("Requested drive %s in boot drive order doesn't exist "
                            "or cannot be used.", drive)

        # Apply the drive order.
        log.debug("Applying drive order: %s", valid_disks)
        storage.bootloader.disk_order = valid_disks

        # Update the module.
        if not dry_run and bootloader_proxy.DriveOrder != drive_order:
            bootloader_proxy.DriveOrder = drive_order

    def _check_boot_drive(self, storage, boot_drive, usable_disks):
        """Check the specified boot drive."""
        # Resolve the disk identifier.
        matched_disks = device_matches(boot_drive, devicetree=storage.devicetree, disks_only=True)

        if not matched_disks:
            raise BootLoaderError(_("No match found for given boot drive "
                                    "\"{}\".").format(boot_drive))

        if len(matched_disks) > 1:
            raise BootLoaderError(_("More than one match found for given boot drive "
                                    "\"{}\".").format(boot_drive))

        if matched_disks[0] not in usable_disks:
            raise BootLoaderError(_("Requested boot drive \"{}\" doesn't exist or cannot "
                                    "be used.").format(boot_drive))

    def _find_drive_with_stage1(self, storage, usable_disks):
        """Find a drive with a valid stage1 device."""
        # Search for valid stage1 devices.
        for device in storage.devices:
            if not storage.bootloader.is_valid_stage1_device(device):
                continue

            # Search for usable disks.
            for disk in device.disks:
                drive = disk.name

                if drive not in usable_disks:
                    continue

                log.debug("Found a drive with a valid stage1: %s", drive)
                return drive

        # No usable disk found.
        log.debug("No usable drive with a valid stage1 was found.")
        return None

    def _get_boot_drive(self, storage, bootloader_proxy):
        """Get the boot drive.

        When bootloader doesn't have --boot-drive parameter then use this logic as fallback:

        1) If present, use the first valid disk from driveorder parameter.
        2) If present and usable, use a disk where a valid stage1 device is placed.
        3) Use the first usable disk from Blivet if there is one.
        4) Raise an exception.
        """
        boot_drive = bootloader_proxy.Drive
        drive_order = storage.bootloader.disk_order
        usable_disks_list = self._get_usable_disks(storage)
        usable_disks_set = set(usable_disks_list)

        # Use a disk from --boot-drive.
        if boot_drive:
            log.debug("Use the requested boot drive.")
            self._check_boot_drive(storage, boot_drive, usable_disks_set)
            return boot_drive

        # Or use the first disk from --driveorder.
        if drive_order:
            log.debug("Use the first usable drive from the drive order.")
            return drive_order[0]

        # Or find a disk with a valid stage1 device.
        found_drive = self._find_drive_with_stage1(storage, usable_disks_set)
        if found_drive:
            log.debug("Use a usable drive with a valid stage1 device.")
            return found_drive

        # Or use the first usable drive.
        if usable_disks_list:
            log.debug("Use the first usable drive.")
            return usable_disks_list[0]

        # Or raise an exception.
        raise BootLoaderError("No usable boot drive was found.")

    def _apply_boot_drive(self, storage, bootloader_proxy, dry_run=False):
        """Apply the boot drive."""
        boot_drive = self._get_boot_drive(storage, bootloader_proxy)
        log.debug("Using a boot drive: %s", boot_drive)

        # Apply the boot drive.
        drive = storage.devicetree.resolve_device(boot_drive)
        storage.bootloader.stage1_disk = drive

        # Update the bootloader module.
        if not dry_run and bootloader_proxy.Drive != boot_drive:
            bootloader_proxy.Drive = boot_drive
