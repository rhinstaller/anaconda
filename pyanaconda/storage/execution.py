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
from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.errors import PartitioningError
from blivet.formats.disklabel import DiskLabel
from blivet.static_data import luks_data

from pyanaconda.bootloader.execution import BootloaderExecutor
from pyanaconda.core.constants import AUTOPART_TYPE_DEFAULT
from pyanaconda.kickstart import refreshAutoSwapSize, getEscrowCertificate
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.platform import platform
from pyanaconda.storage import autopart
from pyanaconda.storage.checker import storage_checker
from pyanaconda.storage.utils import get_pbkdf_args


log = get_module_logger(__name__)

__all__ = ["do_kickstart_storage"]


def do_kickstart_storage(storage, data):
    """Setup storage state from the kickstart data.

    :param storage: an instance of the Blivet's storage object
    :param data: an instance of kickstart data
    """
    # Clear partitions.
    clear_partitions(storage)

    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # Snapshot free space now, so that we know how much we had available.
    storage.create_free_space_snapshot()

    # Prepare the boot loader.
    BootloaderExecutor().execute(storage, dry_run=True)

    AutomaticPartitioningExecutor().execute(storage, data)
    CustomPartitioningExecutor().execute(storage, data)

    data.partition.execute(storage, data)
    data.raid.execute(storage, data)
    data.volgroup.execute(storage, data)
    data.logvol.execute(storage, data)
    data.btrfs.execute(storage, data)
    data.mount.execute(storage, data)

    # Set up the snapshot here.
    data.snapshot.setup(storage, data)

    # Set up the boot loader.
    storage.set_up_bootloader()


def clear_partitions(storage):
    """Clear partitions.

    :param storage: instance of the Blivet's storage object
    """
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
    storage.config.clear_part_type = disk_init_proxy.InitializationMode
    storage.config.clear_part_disks = disk_init_proxy.DrivesToClear
    storage.config.clear_part_devices = disk_init_proxy.DevicesToClear
    storage.config.initialize_disks = disk_init_proxy.InitializeLabelsEnabled

    disk_label = disk_init_proxy.DefaultDiskLabel

    if disk_label and not DiskLabel.set_default_label_type(disk_label):
        log.warning("%s is not a supported disklabel type on this platform. "
                    "Using default disklabel %s instead.", disk_label,
                    DiskLabel.get_platform_label_types()[0])

    storage.clear_partitions()


class AutomaticPartitioningExecutor(object):
    """The executor of the automatic partitioning."""

    def execute(self, storage, data):
        """Execute the automatic partitioning.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        # Create the auto partitioning proxy.
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        # Is the auto partitioning enabled?
        if not auto_part_proxy.Enabled:
            return

        # Sets up default auto partitioning. Use clearpart separately if you want it.
        # The filesystem type is already set in the storage.
        refreshAutoSwapSize(storage)
        storage.do_autopart = True

        if auto_part_proxy.Encrypted:
            storage.encrypted_autopart = True
            storage.encryption_passphrase = auto_part_proxy.Passphrase
            storage.encryption_cipher = auto_part_proxy.Cipher
            storage.autopart_add_backup_passphrase = auto_part_proxy.BackupPassphraseEnabled
            storage.autopart_escrow_cert = getEscrowCertificate(
                storage.escrow_certificates,
                auto_part_proxy.Escrowcert
            )

            luks_version = auto_part_proxy.LUKSVersion or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=luks_version,
                pbkdf_type=auto_part_proxy.PBKDF or None,
                max_memory_kb=auto_part_proxy.PBKDFMemory,
                iterations=auto_part_proxy.PBKDFIterations,
                time_ms=auto_part_proxy.PBKDFTime
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            storage.autopart_luks_version = luks_version
            storage.autopart_pbkdf_args = pbkdf_args

        if auto_part_proxy.Type != AUTOPART_TYPE_DEFAULT:
            storage.autopart_type = auto_part_proxy.Type

        autopart.do_autopart(storage, data, min_luks_entropy=MIN_CREATE_ENTROPY)
        report = storage_checker.check(storage)
        report.log(log)

        if report.failure:
            raise PartitioningError("autopart failed: \n" + "\n".join(report.all_errors))


class CustomPartitioningExecutor(object):
    """The executor of the custom partitioning."""

    def execute(self, storage, data):
        """Execute the custom partitioning.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        self._execute_reqpart(storage, data)

    def _execute_reqpart(self, storage, data):
        """Execute the reqpart command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        if not data.reqpart.reqpart:
            return

        log.debug("Looking for platform-specific bootloader requirements.")
        reqs = platform.set_platform_bootloader_reqs()

        if data.reqpart.addBoot:
            log.debug("Looking for platform-specific boot requirements.")
            boot_partitions = platform.set_platform_boot_partition()

            # Blivet doesn't know this - anaconda sets up the default boot fstype
            # in various places in this file. We need to duplicate that here.
            for part in boot_partitions:
                if part.mountpoint == "/boot":
                    part.fstype = storage.default_boot_fstype

            reqs += boot_partitions

        if reqs:
            log.debug("Applying requirements:\n%s", "".join(map(str, reqs)))
            autopart.do_reqpart(storage, reqs)
