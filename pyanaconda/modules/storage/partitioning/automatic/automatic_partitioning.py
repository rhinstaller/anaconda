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
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.size import Size
from blivet.static_data import luks_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.configuration.storage import PartitioningType
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning.automatic.noninteractive_partitioning import \
    NonInteractivePartitioningTask
from pyanaconda.modules.storage.partitioning.automatic.utils import get_candidate_disks, \
    schedule_implicit_partitions, schedule_volumes, schedule_partitions
from pyanaconda.platform import platform
from pyanaconda.storage.partspec import PartSpec
from pyanaconda.storage.utils import get_pbkdf_args
from pyanaconda.core.storage import suggest_swap_size

log = get_module_logger(__name__)

__all__ = ["AutomaticPartitioningTask"]


SERVER_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("2GiB"),
        max_size=Size("15GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin_volume=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        grow=False,
        lv=True,
        encrypted=True
    )
]

WORKSTATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("70GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin_volume=True,
        encrypted=True),
    PartSpec(
        mountpoint="/home",
        size=Size("500MiB"), grow=True,
        required_space=Size("50GiB"),
        btr=True,
        lv=True,
        thin_volume=True,
        encrypted=True),
    PartSpec(
        fstype="swap",
        grow=False,
        lv=True,
        encrypted=True
    )
]


def get_default_partitioning(partitioning_type=None):
    """Get the default partitioning requests.

    :param partitioning_type: a type of the partitioning
    :return: a list of partitioning specs
    """
    if not partitioning_type:
        partitioning_type = conf.storage.default_partitioning

    if partitioning_type is PartitioningType.SERVER:
        return platform.set_default_partitioning() + SERVER_PARTITIONING

    if partitioning_type is PartitioningType.WORKSTATION:
        return platform.set_default_partitioning() + WORKSTATION_PARTITIONING

    raise ValueError("Invalid partitioning type: {}".format(conf.storage.default_partitioning))


class AutomaticPartitioningTask(NonInteractivePartitioningTask):
    """A task for the automatic partitioning configuration."""

    def __init__(self, storage, request: PartitioningRequest):
        """Create a task.

        :param storage: an instance of Blivet
        :param request: an instance of PartitioningRequest
        """
        super().__init__(storage)
        self._request = request

    def _get_initialization_config(self):
        """Get the initialization config.

        FIXME: This is a temporary method.
        """
        config = super()._get_initialization_config()
        # If autopart is selected we want to remove whatever has been created/scheduled
        # to make room for autopart. If custom is selected, we want to leave alone any
        # storage layout the user may have set up before now.
        config.clear_non_existent = True
        return config

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Executing the automatic partitioning.")

        # Get the partitioning scheme.
        scheme = self._request.partitioning_scheme

        # Set the filesystem type.
        fstype = self._request.file_system_type

        if fstype:
            storage.set_default_fstype(fstype)

        # Get the encryption configuration.
        encrypted = self._request.encrypted

        # Get LUKS format args.
        luks_format_args = self._get_luks_format_args(self._storage, self._request)

        # Set the default pbkdf args.
        pbkdf_args = luks_format_args.get('pbkdf_args', None)

        if pbkdf_args and not luks_data.pbkdf_args:
            luks_data.pbkdf_args = pbkdf_args

        # Get the autopart requests.
        requests = self._get_partitioning(storage, self._request.excluded_mount_points)

        # Do the autopart.
        self._do_autopart(storage, scheme, requests, encrypted, luks_format_args)

    @staticmethod
    def _get_luks_format_args(storage, request):
        """Arguments for the LUKS format constructor.

        :param storage: blivet.Blivet instance
        :param request: a partitioning request
        :return: a dictionary of arguments
        """
        if not request.encrypted:
            return {}

        luks_version = request.luks_version or storage.default_luks_version
        escrow_cert = storage.get_escrow_certificate(request.escrow_certificate)

        pbkdf_args = get_pbkdf_args(
            luks_version=luks_version,
            pbkdf_type=request.pbkdf or None,
            max_memory_kb=request.pbkdf_memory,
            iterations=request.pbkdf_iterations,
            time_ms=request.pbkdf_time
        )

        return {
            "passphrase": request.passphrase,
            "cipher": request.cipher,
            "luks_version": luks_version,
            "pbkdf_args": pbkdf_args,
            "escrow_cert": escrow_cert,
            "add_backup_passphrase": request.backup_passphrase_enabled,
        }

    @staticmethod
    def _get_partitioning(storage, excluded_mount_points=()):
        """Get the partitioning requests for autopart.

        :param storage: blivet.Blivet instance
        :param excluded_mount_points: a list of mount points to exclude
        :return: a list of full partitioning specs
        """
        requests = []

        for request in get_default_partitioning():
            # Skip excluded mount points.
            if (request.mountpoint or request.fstype) in excluded_mount_points:
                continue

            # Set the default filesystem type.
            if request.fstype is None:
                request.fstype = storage.get_fstype(request.mountpoint)

            # Update the size of swap.
            if request.fstype == "swap":
                disk_space = storage.get_disk_free_space()
                request.size = suggest_swap_size(disk_space=disk_space)

            requests.append(request)

        return requests

    @staticmethod
    def _do_autopart(storage, scheme, requests, encrypted=False, luks_fmt_args=None):
        """Perform automatic partitioning.

        :param storage: an instance of Blivet
        :param scheme: a type of the partitioning scheme
        :param requests: list of partitioning requests
        :param encrypted: encrypt the scheduled partitions
        :param luks_fmt_args: arguments for the LUKS format constructor
        """
        log.debug("scheme: %s", scheme)
        log.debug("requests:\n%s", "".join([str(p) for p in requests]))
        log.debug("encrypted: %s", encrypted)
        log.debug("storage.disks: %s", [d.name for d in storage.disks])
        log.debug("storage.partitioned: %s",
                  [d.name for d in storage.partitioned if d.format.supported])
        log.debug("all names: %s", [d.name for d in storage.devices])
        log.debug("boot disk: %s", getattr(storage.bootloader.stage1_disk, "name", None))

        disks = get_candidate_disks(storage)
        log.debug("candidate disks: %s", [d.name for d in disks])

        devs = schedule_implicit_partitions(storage, disks, scheme, encrypted, luks_fmt_args)
        devs = schedule_partitions(storage, disks, devs, scheme, requests, encrypted, luks_fmt_args)

        # run the autopart function to allocate and grow partitions
        do_partitioning(storage)
        schedule_volumes(storage, devs, scheme, requests, encrypted)

        # grow LVs
        grow_lvm(storage)

        # only newly added swaps should appear in the fstab
        new_swaps = (dev for dev in storage.swaps if not dev.format.exists)
        storage.set_fstab_swaps(new_swaps)
