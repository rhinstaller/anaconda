#
# DBus interface for a partitioning module.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base.base_template import ModuleInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import PARTITIONING
from pyanaconda.modules.common.containers import DeviceTreeContainer, TaskContainer

__all__ = ["PartitioningInterface"]


@dbus_interface(PARTITIONING.interface_name)
class PartitioningInterface(ModuleInterfaceTemplate):
    """DBus interface for a partitioning module."""

    @property
    def PartitioningMethod(self) -> Str:
        """Type of the partitioning method.

        :return: a name of the method
        """
        return self.implementation.partitioning_method.value

    def GetDeviceTree(self) -> ObjPath:
        """Get the device tree.

        :return: a DBus path to a device tree
        """
        return DeviceTreeContainer.to_object_path(
            self.implementation.get_device_tree()
        )

    def ConfigureWithTask(self) -> ObjPath:
        """Schedule the partitioning actions.

        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_with_task()
        )

    def ValidateWithTask(self) -> ObjPath:
        """Validate the scheduled partitioning.

        Run sanity checks on the current storage model to
        verify if the partitioning is valid.

        The result of the task is a validation report.

        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.validate_with_task()
        )
