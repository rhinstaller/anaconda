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
from pyanaconda.modules.common.structures.validation import ValidationReport
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

    def get_default_file_system(self):
        """Get the default type of a filesystem.

        :return: a filesystem name
        """
        return self.storage.default_fstype

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

    def collect_unused_devices(self):
        """Collect all devices that are not used in existing or new installations.

        :return: a list of device names
        """
        return [d.name for d in utils.collect_unused_devices(self.storage)]

    def collect_unused_mount_points(self):
        """Collect mount points that can be assigned to a device.

        :return: a list of mount points
        """
        return [m for m in utils.collect_mount_points() if m not in self.storage.mountpoints]

    def collect_boot_loader_devices(self, boot_drive):
        """Collect the boot loader devices.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device names
        """
        return [d.name for d in utils.collect_bootloader_devices(self.storage, boot_drive)]

    def collect_supported_systems(self):
        """Collect supported existing or new installations.

        :return: a list of data about found installations
        """
        return list(map(self._get_os_data, utils.collect_roots(self.storage)))

    def get_supported_raid_levels(self, device_type):
        """Get RAID levels for the specified device type.

        :param device_type: a type of the device
        :return: a list of RAID level names
        """
        return sorted([level.name for level in utils.get_supported_raid_levels(device_type)])

    def validate_mount_point(self, mount_point):
        """Validate the given mount point.

        :param mount_point: a path to a mount point
        :return: a validation report
        """
        report = ValidationReport()
        mount_points = self.storage.mountpoints.keys()
        error = utils.validate_mount_point(mount_point, mount_points)

        if error:
            report.error_messages.append(error)

        return report

    def validate_raid_level(self, raid_level, num_members):
        """Validate the given RAID level.

        :param raid_level: a RAID level name
        :param num_members: a number of members
        :return: a validation report
        """
        report = ValidationReport()
        raid_level = utils.get_raid_level_by_name(raid_level)
        error = utils.validate_raid_level(raid_level, num_members)

        if error:
            report.error_messages.append(error)

        return report

    def validate_container_name(self, name):
        """Validate the given container name.

        :param name: a container name
        :return: a validation report
        """
        report = ValidationReport()
        error = utils.validate_container_name(self.storage, name)

        if error:
            report.error_messages.append(error)

        return report

    def add_device(self, request):
        """Add a new device to the storage model.

        :param request: a device factory request
        :raise: StorageError if the device cannot be created
        """
        utils.add_device(self.storage, request)
