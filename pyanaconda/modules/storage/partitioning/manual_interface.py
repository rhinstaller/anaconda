#
# DBus interface for the manual partitioning module.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.constants import MOUNT_POINT_PATH, MOUNT_POINT_DEVICE, MOUNT_POINT_FORMAT, \
    MOUNT_POINT_REFORMAT, MOUNT_POINT_FORMAT_OPTIONS, MOUNT_POINT_MOUNT_OPTIONS
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface


@dbus_interface(MANUAL_PARTITIONING.interface_name)
class ManualPartitioningInterface(PartitioningInterface):
    """DBus interface for the manual partitioning module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Enabled", self.implementation.enabled_changed)
        self.watch_property("MountPoints", self.implementation.mount_points_changed)

    @property
    def Enabled(self) -> Bool:
        """Is the manual partitioning enabled?"""
        return self.implementation.enabled

    @emits_properties_changed
    def SetEnabled(self, enabled: Bool):
        """Is the manual partitioning enabled?

        :param enabled: True if enabled, otherwise False
        """
        self.implementation.set_enabled(enabled)

    @property
    def MountPoints(self) -> List[Dict[Str, Variant]]:
        """List of mount point assignments."""
        return [{
            MOUNT_POINT_PATH: get_variant(Str, point.mount_point),
            MOUNT_POINT_DEVICE: get_variant(Str, point.device),
            MOUNT_POINT_REFORMAT: get_variant(Bool, point.reformat),
            MOUNT_POINT_FORMAT: get_variant(Str, point.new_format),
            MOUNT_POINT_FORMAT_OPTIONS: get_variant(Str, point.format_options),
            MOUNT_POINT_MOUNT_OPTIONS: get_variant(Str, point.mount_options)
        } for point in self.implementation.mount_points]

    @emits_properties_changed
    def SetMountPoints(self, mount_points: List[Dict[Str, Variant]]):
        """Set the mount point assignments."""
        mount_point_objects = []

        for data in mount_points:
            mount_point = self.implementation.get_new_mount_point()

            if MOUNT_POINT_PATH in data:
                mount_point.set_mount_point(data[MOUNT_POINT_PATH])

            if MOUNT_POINT_DEVICE in data:
                mount_point.set_device(data[MOUNT_POINT_DEVICE])

            if MOUNT_POINT_REFORMAT in data:
                mount_point.set_reformat(data[MOUNT_POINT_REFORMAT])

            if MOUNT_POINT_FORMAT in data:
                mount_point.set_new_format(data[MOUNT_POINT_FORMAT])

            if MOUNT_POINT_FORMAT_OPTIONS in data:
                mount_point.set_format_options(data[MOUNT_POINT_FORMAT_OPTIONS])

            if MOUNT_POINT_MOUNT_OPTIONS in data:
                mount_point.set_mount_options(data[MOUNT_POINT_MOUNT_OPTIONS])

            mount_point_objects.append(mount_point)

        self.implementation.set_mount_points(mount_point_objects)
