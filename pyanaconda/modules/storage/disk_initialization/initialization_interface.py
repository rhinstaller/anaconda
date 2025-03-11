#
# DBus interface for the disk initialization module.
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
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.storage.constants import InitializationMode


@dbus_interface(DISK_INITIALIZATION.interface_name)
class DiskInitializationInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the disk initialization module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("InitializationMode", self.implementation.initialization_mode_changed)
        self.watch_property("DevicesToClear", self.implementation.devices_to_clear_changed)
        self.watch_property("DrivesToClear", self.implementation.drives_to_clear_changed)
        self.watch_property("DefaultDiskLabel", self.implementation.default_disk_label_changed)
        self.watch_property("FormatLDLEnabled", self.implementation.format_ldl_enabled_changed)
        self.watch_property("FormatUnrecognizedEnabled",
                            self.implementation.format_unrecognized_enabled_changed)
        self.watch_property("InitializeLabelsEnabled",
                            self.implementation.initialize_labels_enabled_changed)

    @property
    def InitializationMode(self) -> Int:
        """The initialization mode."""
        return self.implementation.initialization_mode.value

    @InitializationMode.setter
    @emits_properties_changed
    def InitializationMode(self, mode: Int):
        """Set the initialization mode.

        Allowed values:
           -1  Use the default mode.
            0  Do not remove any partitions.
            1  Remove all partitions from the system.
            2  Remove the specified partitions.
            3  Remove all Linux partitions.

        :param mode: a number of the mode
        """
        self.implementation.set_initialization_mode(InitializationMode(mode))

    @property
    def DevicesToClear(self) -> List[Str]:
        """The list of devices to clear."""
        return self.implementation.devices_to_clear

    @DevicesToClear.setter
    @emits_properties_changed
    def DevicesToClear(self, devices: List[Str]):
        """Set the list of devices to clear.

        :param devices: a list of device names
        """
        self.implementation.set_devices_to_clear(devices)

    @property
    def DrivesToClear(self) -> List[Str]:
        """The list of drives to clear."""
        return self.implementation.drives_to_clear

    @DrivesToClear.setter
    @emits_properties_changed
    def DrivesToClear(self, drives: List[Str]):
        """Set the list of drives to clear.

        :param drives: a list of drive names
        """
        self.implementation.set_drives_to_clear(drives)

    @property
    def DefaultDiskLabel(self) -> Str:
        """The default disk label."""
        return self.implementation.default_disk_label

    @DefaultDiskLabel.setter
    @emits_properties_changed
    def DefaultDiskLabel(self, label: Str):
        """Set the default disk label to use.

        :param label: a disk label
        """
        self.implementation.set_default_disk_label(label)

    @property
    def FormatUnrecognizedEnabled(self) -> Bool:
        """Can be disks whose formatting is unrecognized initialized?"""
        return self.implementation.format_unrecognized_enabled

    @FormatUnrecognizedEnabled.setter
    @emits_properties_changed
    def FormatUnrecognizedEnabled(self, value: Bool):
        """Can be disks whose formatting is unrecognized initialized?

        This will destroy all of the contents of disks with invalid partition tables
        or other formatting unrecognizable to the installer. It is useful so that the
        installation program does not ask if it should initialize the disk label if
        installing to a brand new hard drive.

        :param value: True if it is allowed, otherwise False
        """
        self.implementation.set_format_unrecognized_enabled(value)

    @property
    def InitializeLabelsEnabled(self) -> Bool:
        """Can be the disk label initialized to the default for your architecture?"""
        return self.implementation.initialize_labels_enabled

    @InitializeLabelsEnabled.setter
    @emits_properties_changed
    def InitializeLabelsEnabled(self, value: Bool):
        """Can be the disk label initialized to the default for your architecture?

        :param value: True if allowed, otherwise False
        """
        self.implementation.set_initialize_labels_enabled(value)

    @property
    def FormatLDLEnabled(self) -> Bool:
        """Can be LDL DASDs formatted to CDL format?"""
        return self.implementation.format_ldl_enabled

    @FormatLDLEnabled.setter
    @emits_properties_changed
    def FormatLDLEnabled(self, value: Bool):
        """Can be LDL DASDs formatted to CDL format?

        Allow to reformat any LDL DASDs to CDL format.

        :param value: True if allowed, otherwise False
        """
        self.implementation.set_format_ldl_enabled(value)
