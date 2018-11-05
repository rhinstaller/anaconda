#
# Copyright (C) 2018  Red Hat, Inc.
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
from blivet.size import Size
from pyanaconda.core.constants import STORAGE_SWAP_IS_RECOMMENDED

from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.storage.partspec import PartSpec

# Partitioning requirements for servers.
SERVER_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("2GiB"),
        max_size=Size("15GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        grow=False,
        lv=True,
        encrypted=True
    )
]

# Partitioning requirements for workstations.
WORKSTATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("50GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True),
    PartSpec(
        mountpoint="/home",
        size=Size("500MiB"), grow=True,
        required_space=Size("50GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True),
    PartSpec(
        fstype="swap",
        grow=False,
        lv=True,
        encrypted=True
    )
]


def get_full_partitioning_requests(storage, platform, requests):
    """Get the full partitioning requests.

    :param storage: the Blivet's storage object
    :param platform: the current platform object
    :param requests: a list of partitioning specs
    :return:
    """
    requests = _get_platform_specific_partitioning(platform, requests)
    requests = _complete_partitioning_requests(storage, requests)
    requests = _filter_default_partitions(requests)
    return requests


def _get_platform_specific_partitioning(platform, requests):
    """Get the platform-specific partitioning.

    The requests will be completed with the platform-specific
    requirements.

    :param platform: the current platform object
    :param requests: a list of partitioning specs
    """
    return platform.set_default_partitioning() + requests


def _complete_partitioning_requests(storage, requests):
    """Complete the partitioning requests.

    :param storage: the Blivet's storage object
    :param requests: a list of partitioning specs
    :return:
    """
    for request in requests:
        if request.fstype is None:
            request.fstype = storage.get_fstype(request.mountpoint)

    return requests


def _filter_default_partitions(requests):
    """Filter default partitions based on the kickstart data.

    :param requests: a list of requests
    :return: a customized list of requests
    """
    auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)
    skipped_mountpoints = set()
    skipped_fstypes = set()

    # Create sets of mountpoints and fstypes to remove from autorequests.
    if auto_part_proxy.Enabled:
        # Remove /home if --nohome is selected.
        if auto_part_proxy.NoHome:
            skipped_mountpoints.add("/home")

        # Remove /boot if --noboot is selected.
        if auto_part_proxy.NoBoot:
            skipped_mountpoints.add("/boot")

        # Remove swap if --noswap is selected.
        if auto_part_proxy.NoSwap:
            skipped_fstypes.add("swap")

            # Swap will not be recommended by the storage checker.
            # TODO: Remove this code from this function.
            from pyanaconda.storage_utils import storage_checker
            storage_checker.add_constraint(STORAGE_SWAP_IS_RECOMMENDED, False)

    # Skip mountpoints we want to remove.
    return [
        req for req in requests
        if req.mountpoint not in skipped_mountpoints
           and req.fstype not in skipped_fstypes
    ]
