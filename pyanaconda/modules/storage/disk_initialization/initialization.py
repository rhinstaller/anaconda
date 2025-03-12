#
# Disk initialization module.
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
from pykickstart.constants import (
    CLEARPART_TYPE_ALL,
    CLEARPART_TYPE_LINUX,
    CLEARPART_TYPE_LIST,
    CLEARPART_TYPE_NONE,
)

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.storage.constants import InitializationMode
from pyanaconda.modules.storage.disk_initialization.initialization_interface import (
    DiskInitializationInterface,
)
from pyanaconda.modules.storage.storage_subscriber import StorageSubscriberModule

log = get_module_logger(__name__)


class DiskInitializationModule(StorageSubscriberModule):
    """The disk initialization module."""

    def __init__(self):
        super().__init__()

        self.format_unrecognized_enabled_changed = Signal()
        self._format_unrecognized_enabled = False

        self.format_ldl_enabled_changed = Signal()
        self._format_ldl_enabled = False

        self.initialize_labels_enabled_changed = Signal()
        self._initialize_labels_enabled = False

        self.default_disk_label_changed = Signal()
        self._default_disk_label = ""

        self.initialization_mode_changed = Signal()
        self._initialization_mode = InitializationMode.DEFAULT

        self.devices_to_clear_changed = Signal()
        self._devices_to_clear = []

        self.drives_to_clear_changed = Signal()
        self._drives_to_clear = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DISK_INITIALIZATION.object_path,
                            DiskInitializationInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_format_unrecognized_enabled(data.zerombr.zerombr)
        self.set_default_disk_label(data.clearpart.disklabel)
        self.set_initialize_labels_enabled(data.clearpart.initAll)
        self.set_format_ldl_enabled(data.clearpart.cdl)

        mode = self._map_clearpart_type(data.clearpart.type)
        self.set_initialization_mode(mode)

        self.set_devices_to_clear(data.clearpart.devices)
        self.set_drives_to_clear(data.clearpart.drives)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        self._setup_kickstart_from_module(data)
        self._setup_kickstart_from_storage(data)

    def _setup_kickstart_from_module(self, data):
        """Update the configuration from the module.

        :param data: an instance of kickstart data
        """
        data.zerombr.zerombr = self.format_unrecognized_enabled
        data.clearpart.disklabel = self.default_disk_label
        data.clearpart.initAll = self.initialize_labels_enabled
        data.clearpart.cdl = self.format_ldl_enabled

        data.clearpart.type = self._map_clearpart_type(self.initialization_mode, reverse=True)
        data.clearpart.devices = self.devices_to_clear
        data.clearpart.drives = self.drives_to_clear

    def _setup_kickstart_from_storage(self, data):
        """Update the configuration from the partitioned storage.

        :param data: an instance of kickstart data
        """
        # Do nothing without the storage model.
        if not self._storage:
            return

        # Do nothing if the mode is not set to CLEAR_NONE for some reason.
        if self.initialization_mode != InitializationMode.CLEAR_NONE:
            return

        # Find the initialized disks and removed partitions.
        mode, drives, devices = self._find_cleared_devices(self.storage)

        # Update the kickstart data.
        data.clearpart.type = self._map_clearpart_type(mode, reverse=True)
        data.clearpart.devices = devices
        data.clearpart.drives = drives

    def _map_clearpart_type(self, value, reverse=False):
        """Convert the clearpart type to the initialization mode.

        :param value: a value to convert
        :param reverse: reverse the direction
        :return: a converted value
        """
        mapping = {
            None: InitializationMode.DEFAULT,
            CLEARPART_TYPE_NONE: InitializationMode.CLEAR_NONE,
            CLEARPART_TYPE_ALL: InitializationMode.CLEAR_ALL,
            CLEARPART_TYPE_LIST: InitializationMode.CLEAR_LIST,
            CLEARPART_TYPE_LINUX: InitializationMode.CLEAR_LINUX
        }

        if reverse:
            mapping = {v: k for k, v in mapping.items()}

        return mapping[value]

    @property
    def initialization_mode(self):
        """The initialization mode."""
        return self._initialization_mode

    def set_initialization_mode(self, mode):
        """Set the initialization mode.

        :param mode: an instance of InitializationMode
        """
        self._initialization_mode = mode
        self.initialization_mode_changed.emit()
        log.debug("The initialization mode is set to '%s'.", mode)

    @property
    def devices_to_clear(self):
        """The list of devices to clear."""
        return self._devices_to_clear

    def set_devices_to_clear(self, devices):
        """Set the list of devices to clear.

        :param devices: a list of devices names
        """
        self._devices_to_clear = devices
        self.devices_to_clear_changed.emit()
        log.debug("Devices to clear are set to '%s'.", devices)

    @property
    def drives_to_clear(self):
        """The list of drives to clear."""
        return self._drives_to_clear

    def set_drives_to_clear(self, drives):
        """Set the list of drives to clear.

        :param drives: a list of drive names
        """
        self._drives_to_clear = drives
        self.drives_to_clear_changed.emit()
        log.debug("Drives to clear are set to '%s'.", drives)

    @property
    def default_disk_label(self):
        """The default disk label."""
        return self._default_disk_label

    def set_default_disk_label(self, label):
        """Set the default disk label to use.

        :param label: a disk label
        """
        self._default_disk_label = label
        self.default_disk_label_changed.emit()
        log.debug("Default disk label is set to '%s'.", label)

    @property
    def format_unrecognized_enabled(self):
        """Can be disks whose formatting is unrecognized initialized?"""
        return self._format_unrecognized_enabled

    def set_format_unrecognized_enabled(self, value):
        """Can be disks whose formatting is unrecognized initialized?

        :param value: True if allowed, otherwise False
        """
        self._format_unrecognized_enabled = value
        self.format_unrecognized_enabled_changed.emit(value)
        log.debug("Can format unrecognized is set to '%s'.", value)

    @property
    def initialize_labels_enabled(self):
        """Can be the disk label initialized to the default for your architecture?"""
        return self._initialize_labels_enabled

    def set_initialize_labels_enabled(self, value):
        """Can be the disk labels initialized to the default for your architecture?

        :param value: True if allowed, otherwise False
        """
        self._initialize_labels_enabled = value
        self.initialize_labels_enabled_changed.emit()
        log.debug("Can initialize labels is set to '%s'.", value)

    @property
    def format_ldl_enabled(self):
        """Can be LDL DASDs formatted to CDL format?"""
        return self._format_ldl_enabled

    def set_format_ldl_enabled(self, value):
        """Can be LDL DASDs formatted to CDL format?

        :param value: True if allowed, otherwise False
        """
        self._format_ldl_enabled = value
        self.format_ldl_enabled_changed.emit(value)
        log.debug("Can format LDL is set to '%s'.", value)

    @staticmethod
    def _find_cleared_devices(storage):
        """Find initialized disks and removed partitions.

        Make a list of initialized disks and of removed partitions. If any
        partitions were removed from disks that were not completely cleared
        we'll have to use CLEAR_LIST and provide a list of all removed
        partitions. If no partitions were removed from a disk that was not
        cleared/reinitialized we can use CLEAR_ALL.

        :param storage: an instance of the storage
        :return: a new initialization mode, a list of disks and a list of partitions
        """
        destroy_actions = storage.devicetree.actions.find(
            action_type="destroy",
            object_type="device"
        )

        cleared_disks = [
            disk.name for disk in storage.disks
            if disk.partitioned and not disk.format.exists
        ]

        cleared_partitions = [
            action.device.name for action in destroy_actions
            if action.device.type == "partition"
        ]

        cleared_all = all(
            name for name in cleared_partitions if name in cleared_disks
        )

        if not destroy_actions:
            return InitializationMode.CLEAR_NONE, [], []
        elif cleared_all:
            return InitializationMode.CLEAR_ALL, cleared_disks, []
        else:
            return InitializationMode.CLEAR_LIST, [], cleared_partitions
