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
from blivet.formats import get_format
from pykickstart.errors import KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import MOUNT_POINT_DEVICE, MOUNT_POINT_REFORMAT, MOUNT_POINT_FORMAT, \
    MOUNT_POINT_PATH, MOUNT_POINT_FORMAT_OPTIONS, MOUNT_POINT_MOUNT_OPTIONS
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.noninteractive_partitioning import \
    NonInteractivePartitioningTask

log = get_module_logger(__name__)

__all__ = ["ManualPartitioningTask"]


class ManualPartitioningTask(NonInteractivePartitioningTask):
    """A task for the manual partitioning configuration."""

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Setting up the mount points.")
        manual_part_proxy = STORAGE.get_proxy(MANUAL_PARTITIONING)

        # Disable automatic partitioning.
        storage.do_autopart = False

        # Set up mount points.
        for mount_data in manual_part_proxy.MountPoints:
            self._setup_mount_point(storage, mount_data)

    def _setup_mount_point(self, storage, mount_data):
        """Set up a mount point.

        :param storage: an instance of the Blivet's storage object
        :param mount_data: an instance of MountData
        """
        device = mount_data[MOUNT_POINT_DEVICE]
        device_reformat = mount_data[MOUNT_POINT_REFORMAT]
        device_format = mount_data[MOUNT_POINT_FORMAT]

        dev = storage.devicetree.resolve_device(device)
        if dev is None:
            raise KickstartParseError(_("Unknown or invalid device '%s' specified") % device)

        if device_reformat:
            if device_format:
                fmt = get_format(device_format)

                if not fmt:
                    raise KickstartParseError(
                        _("Unknown or invalid format '%(format)s' specified for device "
                          "'%(device)s'") % {"format": device_format, "device": device}
                    )
            else:
                old_fmt = dev.format

                if not old_fmt or old_fmt.type is None:
                    raise KickstartParseError(_("No format on device '%s'") % device)

                fmt = get_format(old_fmt.type)
            storage.format_device(dev, fmt)
            # make sure swaps end up in /etc/fstab
            if fmt.type == "swap":
                storage.add_fstab_swap(dev)

        # only set mount points for mountable formats
        mount_point = mount_data[MOUNT_POINT_PATH]

        if dev.format.mountable and mount_point and mount_point != "none":
            dev.format.mountpoint = mount_point

        dev.format.create_options = mount_data[MOUNT_POINT_FORMAT_OPTIONS]
        dev.format.options = mount_data[MOUNT_POINT_MOUNT_OPTIONS]
