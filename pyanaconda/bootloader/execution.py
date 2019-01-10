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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import blivet.arch
from blivet.devices import iScsiDiskDevice
from pykickstart.errors import KickstartParseError

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import BOOTLOADER_ENABLED, BOOTLOADER_SKIPPED, \
    BOOTLOADER_LOCATION_PARTITION, BOOTLOADER_TIMEOUT_UNSET
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.storage.utils import device_matches

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["BootloaderExecutor"]


class BootloaderExecutor(object):
    """The executor of the bootloader command."""

    def execute(self, storage, dry_run=False):
        """Resolve and execute the bootloader installation.

        :param storage: object storing storage-related information
                        (disks, partitioning, bootloader, etc.)
        :param dry_run: flag if this is only dry run before the partitioning
                        will be resolved
        """
        log.debug("Execute the bootloader with dry run %s.", dry_run)
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

        # Skip bootloader for s390x image installation.
        if blivet.arch.is_s390() \
                and conf.target.is_image \
                and bootloader_proxy.BootloaderMode == BOOTLOADER_ENABLED:
            bootloader_proxy.SetBootloaderMode(BOOTLOADER_SKIPPED)

        # Is the bootloader enabled?
        if bootloader_proxy.BootloaderMode != BOOTLOADER_ENABLED:
            storage.bootloader.skip_bootloader = True
            log.debug("Bootloader is not enabled, skipping.")
            return

        # Apply the settings.
        self._update_flags(storage, bootloader_proxy)
        self._apply_args(storage, bootloader_proxy)
        self._apply_location(storage, bootloader_proxy)
        self._apply_password(storage, bootloader_proxy)
        self._apply_timeout(storage, bootloader_proxy)
        self._apply_drive_order(storage, bootloader_proxy, dry_run=dry_run)
        self._apply_boot_drive(storage, bootloader_proxy, dry_run=dry_run)

    def _update_flags(self, storage, bootloader_proxy):
        """Update flags."""
        if bootloader_proxy.KeepMBR:
            log.debug("Don't update the MBR.")
            storage.bootloader.keep_mbr = True

        if bootloader_proxy.KeepBootOrder:
            log.debug("Don't change the existing boot order.")
            storage.bootloader.keep_boot_order = True

    def _apply_args(self, storage, bootloader_proxy):
        """Apply the arguments."""
        args = bootloader_proxy.ExtraArguments
        log.debug("Applying bootloader arguments: %s", args)
        storage.bootloader.boot_args.update(args)

    def _apply_location(self, storage, bootloader_proxy):
        """Set the location."""
        location = bootloader_proxy.PreferredLocation
        log.debug("Applying bootloader location: %s", location)

        storage.bootloader.set_preferred_stage1_type(
            "boot" if location == BOOTLOADER_LOCATION_PARTITION else "mbr"
        )

    def _apply_password(self, storage, bootloader_proxy):
        """Set the password."""
        if bootloader_proxy.IsPasswordSet:
            log.debug("Applying bootloader password.")

            if bootloader_proxy.IsPasswordEncrypted:
                storage.bootloader.encrypted_password = bootloader_proxy.Password
            else:
                storage.bootloader.password = bootloader_proxy.Password

    def _apply_timeout(self, storage, bootloader_proxy):
        """Set the timeout."""
        timeout = bootloader_proxy.Timeout
        if timeout != BOOTLOADER_TIMEOUT_UNSET:
            log.debug("Applying bootloader timeout: %s", timeout)
            storage.bootloader.timeout = timeout

    def _is_usable_disk(self, d):
        """Is the disk usable for the bootloader?

        Throw out drives that don't exist or cannot be used
        (iSCSI device on an s390 machine).
        """
        return \
            not d.format.hidden and \
            not d.protected and \
            not (blivet.arch.is_s390() and isinstance(d, iScsiDiskDevice))

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
            bootloader_proxy.SetDriveOrder(drive_order)

    def _check_boot_drive(self, storage, boot_drive, usable_disks):
        """Check the specified boot drive."""
        # Resolve the disk identifier.
        matched_disks = device_matches(boot_drive, devicetree=storage.devicetree, disks_only=True)

        if not matched_disks:
            raise KickstartParseError(_("No match found for given boot drive "
                                        "\"{}\".").format(boot_drive))

        if len(matched_disks) > 1:
            raise KickstartParseError(_("More than one match found for given boot drive "
                                        "\"{}\".").format(boot_drive))

        if matched_disks[0] not in usable_disks:
            raise KickstartParseError(_("Requested boot drive \"{}\" doesn't exist or cannot "
                                        "be used.").format(boot_drive))

    def _find_drive_with_boot(self, storage, usable_disks):
        """Find a drive with the /boot partition."""
        # Find a device for /boot.
        device = storage.mountpoints.get("/boot", None)

        if not device:
            log.debug("The /boot partition doesn't exist.")
            return None

        # Use a disk of the device.
        if device.disks:
            drive = device.disks[0].name

            if drive in usable_disks:
                log.debug("Found a boot drive: %s", drive)
                return drive

        # No usable disk found.
        log.debug("No usable drive with /boot was found.")
        return None

    def _get_boot_drive(self, storage, bootloader_proxy):
        """Apply the boot drive.

        When bootloader doesn't have --boot-drive parameter then use this logic as fallback:
        1) If present first valid disk from driveorder parameter
        2) If present and usable, use disk where /boot partition is placed
        3) Use first disk from Blivet
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

        # Or find a disk with the /boot partition.
        found_drive = self._find_drive_with_boot(storage, usable_disks_set)
        if found_drive:
            log.debug("Use a usable drive with a /boot partition.")
            return found_drive

        # Or use the first usable drive.
        log.debug("Use the first usable drive.")
        return usable_disks_list[0]

    def _apply_boot_drive(self, storage, bootloader_proxy, dry_run=False):
        """Apply the boot drive.

        When bootloader doesn't have --boot-drive parameter then use this logic as fallback:

        1) If present first valid disk from --driveorder parameter.
        2) If present and usable, use disk where /boot partition is placed.
        3) Use first disk from Blivet.
        """
        boot_drive = self._get_boot_drive(storage, bootloader_proxy)
        log.debug("Using a boot drive: %s", boot_drive)

        # Apply the boot drive.
        drive = storage.devicetree.resolve_device(boot_drive)
        storage.bootloader.stage1_disk = drive

        # Update the bootloader module.
        if not dry_run and bootloader_proxy.Drive != boot_drive:
            bootloader_proxy.SetDrive(boot_drive)
