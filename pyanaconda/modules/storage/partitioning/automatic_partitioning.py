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
from blivet.static_data import luks_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.noninteractive_partitioning import \
    NonInteractivePartitioningTask
from pyanaconda.storage import autopart
from pyanaconda.storage.utils import get_pbkdf_args

log = get_module_logger(__name__)

__all__ = ["AutomaticPartitioningTask"]


class AutomaticPartitioningTask(NonInteractivePartitioningTask):
    """A task for the automatic partitioning configuration."""

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Executing the automatic partitioning.")

        # Create the auto partitioning proxy.
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        # Enable automatic partitioning.
        storage.do_autopart = True

        # Set the filesystem type.
        fstype = auto_part_proxy.FilesystemType

        if fstype:
            storage.set_default_fstype(fstype)
            storage.set_default_boot_fstype(fstype)

        # Set the encryption.
        if auto_part_proxy.Encrypted:
            storage.encrypted_autopart = True
            storage.encryption_passphrase = auto_part_proxy.Passphrase
            storage.encryption_cipher = auto_part_proxy.Cipher
            storage.autopart_add_backup_passphrase = auto_part_proxy.BackupPassphraseEnabled
            storage.autopart_escrow_cert = storage.get_escrow_certificate(auto_part_proxy.Escrowcert)

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

        storage.autopart_type = auto_part_proxy.Type

        autopart.do_autopart(storage, min_luks_entropy=MIN_CREATE_ENTROPY)
