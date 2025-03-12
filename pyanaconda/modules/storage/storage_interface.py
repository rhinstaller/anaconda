#
# DBus interface for the storage.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.containers import PartitioningContainer, TaskContainer
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod


@dbus_interface(STORAGE.interface_name)
class StorageInterface(KickstartModuleInterface):
    """DBus interface for Storage module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property(
            "CreatedPartitioning", self.implementation.created_partitioning_changed
        )
        self.watch_property(
            "AppliedPartitioning", self.implementation.applied_partitioning_changed
        )

    def ScanDevicesWithTask(self) -> ObjPath:
        """Scan all devices with a task.

        Create a model of the current storage. This model will be used
        to schedule partitioning actions and validate the planned
        partitioning layout. See the CreatePartitioning method.

        :return: a path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.scan_devices_with_task()
        )

    @emits_properties_changed
    def CreatePartitioning(self, method: Str) -> ObjPath:
        """Create a new partitioning.

        Create a new partitioning module with its own copy of the current
        storage model. The partitioning module provides an isolated
        playground for scheduling partitioning actions and validating
        the planned partitioning layout. Once the layout is valid, call
        ApplyPartitioning to choose it for the installation.

        Allowed values:
            AUTOMATIC
            CUSTOM
            MANUAL
            INTERACTIVE
            BLIVET

        :param method: a partitioning method
        :return: a path to a partitioning
        """
        return PartitioningContainer.to_object_path(
            self.implementation.create_partitioning(PartitioningMethod(method))
        )

    @property
    def CreatedPartitioning(self) -> List[ObjPath]:
        """List of all created partitioning modules.

        :return: a list of DBus paths
        """
        return PartitioningContainer.to_object_path_list(
            self.implementation.created_partitioning
        )

    @emits_properties_changed
    def ApplyPartitioning(self, partitioning: ObjPath):
        """Apply the partitioning.

        Choose a valid partitioning layout of the specified partitioning
        module for an installation. Call InstallWithTasks to execute the
        scheduled actions and commit these changes to selected disks.

        The device tree module provides information about the partitioned
        storage model instead of the model of the current storage if there
        is an applied partitioning.

        :param partitioning: a path to a partitioning
        :raise: InvalidStorageError if the partitioning is not valid
        """
        self.implementation.apply_partitioning(
            PartitioningContainer.from_object_path(partitioning)
        )

    @property
    def AppliedPartitioning(self) -> Str:
        """The applied partitioning.

        An empty string is not a valid object path, so
        the return type has to be a string in this case.

        :return: a DBus path or an empty string
        """
        partitioning = self.implementation.applied_partitioning

        if not partitioning:
            return ""

        return PartitioningContainer.to_object_path(partitioning)

    @emits_properties_changed
    def ResetPartitioning(self):
        """Reset the scheduled partitioning.

        Reset the applied partitioning and reset the storage models of all
        partitioning modules to the latest model of the system's storage
        configuration.

        This method will not rescan the system.
        """
        self.implementation.reset_partitioning()

    def WriteConfigurationWithTask(self) -> ObjPath:
        """Write the storage configuration with a task.

        FIXME: This is a temporary workaround.

        :return: an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.write_configuration_with_task()
        )
