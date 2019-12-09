#
# DBus interface for the device tree scheduler
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_SCHEDULER
from pyanaconda.modules.common.structures.storage import OSData
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface

__all__ = ["DeviceTreeSchedulerInterface"]


@dbus_interface(DEVICE_TREE_SCHEDULER.interface_name)
class DeviceTreeSchedulerInterface(DeviceTreeInterface):
    """DBus interface for the device tree scheduler."""

    def GenerateSystemName(self) -> Str:
        """Generate a name of the new installation.

        :return: a translated string
        """
        return self.implementation.generate_system_name()

    def GenerateSystemData(self, boot_drive: Str) -> Structure:
        """Generate the new installation data.

        :param boot_drive: a name of the boot drive
        :return: a structure with data about the new installation
        """
        return OSData.to_structure(
            self.implementation.generate_system_data(boot_drive)
        )

    def GetPartitioned(self) -> List[Str]:
        """Get all partitioned devices in the device tree.

        :return: a list of device names
        """
        return self.implementation.get_partitioned()

    def CollectNewDevices(self, boot_drive: Str) -> List[Str]:
        """Get all new devices in the device tree.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device names
        """
        return self.implementation.collect_new_devices(boot_drive)
