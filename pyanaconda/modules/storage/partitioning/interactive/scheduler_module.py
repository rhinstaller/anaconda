#
# The device tree scheduler
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.partitioning.interactive.scheduler_interface import \
    DeviceTreeSchedulerInterface
from pyanaconda.modules.storage.partitioning.interactive import utils

log = get_module_logger(__name__)

__all__ = ["DeviceTreeSchedulerModule"]


class DeviceTreeSchedulerModule(DeviceTreeModule):
    """The device tree scheduler."""

    def for_publication(self):
        """Return a DBus representation."""
        return DeviceTreeSchedulerInterface(self)

    def generate_system_name(self):
        """Generate a name of the new installation.

        :return: a translated string
        """
        return utils.get_new_root_name()

    def generate_system_data(self, boot_drive):
        """Generate the new installation data.

        :param boot_drive: a name of the boot drive
        :return: an instance of OSData
        """
        root = utils.create_new_root(self.storage, boot_drive)
        return self._get_os_data(root)

    def get_partitioned(self):
        """Get all partitioned devices in the device tree.

        :return: a list of device names
        """
        return [d.name for d in self.storage.partitioned]

    def collect_new_devices(self, boot_drive):
        """Get all new devices in the device tree.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device names
        """
        return [d.name for d in utils.collect_new_devices(self.storage, boot_drive)]
