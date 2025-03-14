#
# DBus interface for the disk selection module.
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

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.structures.validation import ValidationReport


@dbus_interface(DISK_SELECTION.interface_name)
class DiskSelectionInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the disk selection module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("SelectedDisks", self.implementation.selected_disks_changed)
        self.watch_property("ExclusiveDisks", self.implementation.exclusive_disks_changed)
        self.watch_property("IgnoredDisks", self.implementation.ignored_disks_changed)
        self.watch_property("ProtectedDevices", self.implementation.protected_devices_changed)
        self.watch_property("DiskImages", self.implementation.disk_images_changed)

    @property
    def SelectedDisks(self) -> List[Str]:
        """The list of selected disks."""
        return self.implementation.selected_disks

    @SelectedDisks.setter
    @emits_properties_changed
    def SelectedDisks(self, drives: List[Str]):
        """Set the list of selected disks.

        Specifies those disks that anaconda can use for
        partitioning, formatting, and clearing.

        :param drives: a list of drives IDs
        """
        self.implementation.set_selected_disks(drives)

    def ValidateSelectedDisks(self, drives: List[Str]) -> Structure:
        """Validate the list of selected disks.

        :param drives: a list of drives IDs
        :return: a validation report
        """
        return ValidationReport.to_structure(
            self.implementation.validate_selected_disks(drives)
        )

    @property
    def ExclusiveDisks(self) -> List[Str]:
        """The list of drives to scan."""
        return self.implementation.exclusive_disks

    @ExclusiveDisks.setter
    @emits_properties_changed
    def ExclusiveDisks(self, drives: List[Str]):
        """Set the list of drives to scan.

        Specifies those disks that anaconda will scan during
        the storage reset. If the list is empty, anaconda will
        scan all drives.

        It can be set from the kickstart with 'ignoredisk --onlyuse'.

        :param drives: a list of drives IDs
        """
        self.implementation.set_exclusive_disks(drives)

    @property
    def IgnoredDisks(self) -> List[Str]:
        """The list of ignored disks."""
        return self.implementation.ignored_disks

    @IgnoredDisks.setter
    @emits_properties_changed
    def IgnoredDisks(self, drives: List[Str]):
        """Set the list of ignored disks.

        Specifies those disks that anaconda should not touch
        when it does partitioning, formatting, and clearing.

        :param drives: a list of drive IDs
        """
        self.implementation.set_ignored_disks(drives)

    @property
    def ProtectedDevices(self) -> List[Str]:
        """The list of devices to protect."""
        return self.implementation.protected_devices

    @ProtectedDevices.setter
    @emits_properties_changed
    def ProtectedDevices(self, devices: List[Str]):
        """Set the list of protected devices.

        Specifies those disks that anaconda should protect.

        :param devices: a list of device IDs
        """
        self.implementation.set_protected_devices(devices)

    @property
    def DiskImages(self) -> Dict[Str, Str]:
        """The dictionary of disk images."""
        return self.implementation.disk_images

    @DiskImages.setter
    @emits_properties_changed
    def DiskImages(self, disk_images: Dict[Str, Str]):
        """Set the dictionary of disk images.

        :param disk_images: a dictionary of image names and file names
        """
        self.implementation.set_disk_images(disk_images)

    def GetUsableDisks(self) -> List[Str]:
        """Get a list of disks that can be used for the installation.

        :return: a list of disk IDs
        """
        return self.implementation.get_usable_disks()
