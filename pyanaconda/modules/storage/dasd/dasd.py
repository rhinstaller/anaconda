#
# DASD module.
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
from blivet import arch

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.constants.objects import DASD
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.storage.dasd.dasd_interface import DASDInterface
from pyanaconda.modules.storage.dasd.discover import DASDDiscoverTask
from pyanaconda.modules.storage.dasd.format import (
    DASDFormatTask,
    FindFormattableDASDTask,
)
from pyanaconda.modules.storage.storage_subscriber import StorageSubscriberModule

log = get_module_logger(__name__)


class DASDModule(StorageSubscriberModule):
    """The DASD module."""

    def __init__(self):
        super().__init__()
        self._can_format_unformatted = False
        self._can_format_ldl = False

    def publish(self):
        """Publish the module."""
        DBus.publish_object(DASD.object_path, DASDInterface(self))

    def is_supported(self):
        """Is this module supported?"""
        return arch.is_s390()

    def _get_device(self, device_id):
        """Find a device by its ID.

        :param device_id: ID of the device
        :return: an instance of the Blivet's device
        :raise: UnknownDeviceError if no device is found
        """
        device = self.storage.devicetree.get_device_by_device_id(device_id, hidden=True)

        if not device:
            raise UnknownDeviceError(device_id)

        return device

    def _get_devices(self, device_ids):
        """Find devices by their IDs.

        :param device_ids: IDs of the devices
        :return: a list of instances of the Blivet's device
        """
        return list(map(self._get_device, device_ids))

    def on_format_unrecognized_enabled_changed(self, value):
        """Update the flag for formatting unformatted DASDs."""
        self._can_format_unformatted = value

    def on_format_ldl_enabled_changed(self, value):
        """Update the flags for formatting LDL DASDs."""
        self._can_format_ldl = value

    def discover_with_task(self, device_number):
        """Discover a DASD.

        :param device_number: a device number
        :return: a task
        """
        return DASDDiscoverTask(device_number)

    def find_formattable(self, disk_ids):
        """Find DASDs for formatting.

        :param disk_ids: a list of disk IDs to search
        :return: a list of DASDs for formatting
        """
        task = FindFormattableDASDTask(
            self._get_devices(disk_ids),
            self._can_format_unformatted,
            self._can_format_ldl
        )

        found_disks = task.run()
        return [d.device_id for d in found_disks]

    def format_with_task(self, dasds):
        """Format specified DASD disks.

        :param dasds: a list of disk names
        :return: a DBus path to a task
        """
        return DASDFormatTask(dasds)
