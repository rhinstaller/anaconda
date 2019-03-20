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
from blivet.errors import NoDisksError, NotEnoughFreeSpaceError
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.static_data import luks_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.noninteractive_partitioning import \
    NonInteractivePartitioningTask
from pyanaconda.modules.storage.partitioning.schedule import get_candidate_disks, \
    schedule_implicit_partitions, schedule_volumes, schedule_partitions
from pyanaconda.platform import platform
from pyanaconda.storage.partitioning import get_full_partitioning_requests, \
    get_default_partitioning
from pyanaconda.storage.utils import suggest_swap_size

log = get_module_logger(__name__)

__all__ = ["AutomaticPartitioningTask"]


class AutomaticPartitioningTask(NonInteractivePartitioningTask):
    """A task for the automatic partitioning configuration."""

    def __init__(self, storage, scheme, encrypted=False, luks_format_args=None):
        """Create a task.

        :param storage: an instance of Blivet
        :param scheme: a type of the partitioning scheme
        :param encrypted: encrypt the scheduled partitions
        :param luks_format_args: arguments for the LUKS format constructor
        """
        super().__init__(storage)
        self._scheme = scheme
        self._encrypted = encrypted
        self._luks_format_args = luks_format_args or {}

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Executing the automatic partitioning.")

        # Create the auto partitioning proxy.
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        # Set the filesystem type.
        fstype = auto_part_proxy.FilesystemType

        if fstype:
            storage.set_default_fstype(fstype)
            storage.set_default_boot_fstype(fstype)

        # Set the default pbkdf args.
        pbkdf_args = self._luks_format_args.get('pbkdf_args', None)

        if pbkdf_args and not luks_data.pbkdf_args:
            luks_data.pbkdf_args = pbkdf_args

        # Set the minimal entropy.
        min_luks_entropy = self._luks_format_args.get('min_luks_entropy', None)

        if min_luks_entropy is not None:
            luks_data.min_entropy = min_luks_entropy

        # Get the autopart requests.
        requests = self._get_autopart_requests(storage)

        # Do the autopart.
        self._do_autopart(storage, self._scheme, requests, self._encrypted, self._luks_format_args)

    def _get_autopart_requests(self, storage):
        """Get the partitioning requests for autopart.

        :param storage: blivet.Blivet instance
        :return: a list of full partitioning specs
        """
        requests = get_full_partitioning_requests(storage, platform, get_default_partitioning())

        # Update the size of swap.
        for request in requests:
            if request.fstype == "swap":
                disk_space = storage.get_disk_free_space()
                request.size = suggest_swap_size(disk_space=disk_space)
                break

        return requests

    def _do_autopart(self, storage, scheme, requests, encrypted=False, luks_fmt_args=None):
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
        log.debug("clear_part_type: %s", storage.config.clear_part_type)
        log.debug("clear_part_disks: %s", storage.config.clear_part_disks)
        log.debug("storage.disks: %s", [d.name for d in storage.disks])
        log.debug("storage.partitioned: %s", [d.name for d in storage.partitioned if d.format.supported])
        log.debug("all names: %s", [d.name for d in storage.devices])
        log.debug("boot disk: %s", getattr(storage.bootloader.stage1_disk, "name", None))

        if not any(d.format.supported for d in storage.partitioned):
            raise NoDisksError(_("No usable disks selected"))

        disks = get_candidate_disks(storage)
        devs = schedule_implicit_partitions(storage, disks, scheme, encrypted, luks_fmt_args)
        log.debug("candidate disks: %s", disks)
        log.debug("devs: %s", devs)

        if not disks:
            raise NotEnoughFreeSpaceError(_("Not enough free space on disks for "
                                            "automatic partitioning"))

        devs = schedule_partitions(storage, disks, devs, scheme, requests, encrypted, luks_fmt_args)

        # run the autopart function to allocate and grow partitions
        do_partitioning(storage)
        schedule_volumes(storage, devs, scheme, requests, encrypted)

        # grow LVs
        grow_lvm(storage)

        # only newly added swaps should appear in the fstab
        new_swaps = (dev for dev in storage.swaps if not dev.format.exists)
        storage.set_fstab_swaps(new_swaps)
