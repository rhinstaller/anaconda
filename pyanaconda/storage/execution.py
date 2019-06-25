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

from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING, MANUAL_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.automatic_partitioning import \
    AutomaticPartitioningTask
from pyanaconda.modules.storage.partitioning.custom_partitioning import CustomPartitioningTask
from pyanaconda.modules.storage.partitioning.interactive_partitioning import \
    InteractivePartitioningTask
from pyanaconda.modules.storage.partitioning.manual_partitioning import ManualPartitioningTask
from pyanaconda.storage.utils import get_pbkdf_args

__all__ = ["configure_storage"]


def configure_storage(storage, data=None, interactive=False):
    """Setup storage state from the kickstart data.

    :param storage: an instance of the Blivet's storage object
    :param data: an instance of kickstart data or None
    :param interactive: use a task for the interactive partitioning
    """
    auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

    if interactive:
        task = InteractivePartitioningTask(storage)
    elif auto_part_proxy.Enabled:
        luks_version = auto_part_proxy.LUKSVersion or storage.default_luks_version
        passphrase = auto_part_proxy.Passphrase
        escrow_cert = storage.get_escrow_certificate(auto_part_proxy.Escrowcert)

        pbkdf_args = get_pbkdf_args(
            luks_version=luks_version,
            pbkdf_type=auto_part_proxy.PBKDF or None,
            max_memory_kb=auto_part_proxy.PBKDFMemory,
            iterations=auto_part_proxy.PBKDFIterations,
            time_ms=auto_part_proxy.PBKDFTime
        )

        luks_format_args = {
            "passphrase": passphrase,
            "cipher": auto_part_proxy.Cipher,
            "luks_version": luks_version,
            "pbkdf_args": pbkdf_args,
            "escrow_cert": escrow_cert,
            "add_backup_passphrase": auto_part_proxy.BackupPassphraseEnabled,
            "min_luks_entropy": MIN_CREATE_ENTROPY,
        }

        task = AutomaticPartitioningTask(
            storage,
            auto_part_proxy.Type,
            auto_part_proxy.Encrypted,
            luks_format_args
        )
    elif STORAGE.get_proxy(MANUAL_PARTITIONING).Enabled:
        task = ManualPartitioningTask(storage)
    else:
        task = CustomPartitioningTask(storage, data)

    task.run()
