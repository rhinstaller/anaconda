#
# Viewer of the device tree
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
from abc import abstractmethod, ABC

from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceActionData, \
    DeviceFormatData, OSData, MountPointConstraintsData
from pyanaconda.modules.storage.devicetree.utils import get_required_device_size, \
    get_supported_filesystems
from pyanaconda.modules.storage.platform import platform
from pyanaconda.modules.storage.partitioning.specification import PartSpec

log = get_module_logger(__name__)

__all__ = ["DeviceTreeViewer"]


class DeviceTreeViewer(ABC):
    """The viewer of the device tree."""

    @property
    @abstractmethod
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        return None

    def get_root_device(self):
        """Get the root device.

        :return: a name of the root device
        """
        device = self.storage.root_device
        return device.name if device else ""

    def get_devices(self):
        """Get all devices in the device tree.

        :return: a list of device names
        """
        return [d.name for d in self.storage.devices]

    def get_disks(self):
        """Get all disks in the device tree.

        Ignored disks are excluded, as are disks with no media present.

        :return: a list of device names
        """
        return [d.name for d in self.storage.disks]

    def get_mount_points(self):
        """Get all mount points in the device tree.

        :return: a dictionary of mount points and device names
        """
        return {
            mount_point: device.name
            for mount_point, device in self.storage.mountpoints.items()
        }

    def get_device_data(self, name):
        """Get the device data.

        :param name: a device name
        :return: an instance of DeviceData
        :raise: UnknownDeviceError if the device is not found
        """
        # Find the device.
        device = self._get_device(name)

        # Collect the device data.
        data = DeviceData()
        self._set_device_data(device, data)

        # Collect the specialized data.
        if device.type == "dasd":
            self._set_device_data_dasd(device, data)
        elif device.type == "fcoe":
            self._set_device_data_fcoe(device, data)
        elif device.type == "iscsi":
            self._set_device_data_iscsi(device, data)
        elif device.type == "zfcp":
            self._set_device_data_zfcp(device, data)

        # Prune the attributes.
        data.attrs = self._prune_attributes(data.attrs)
        return data

    def _set_device_data(self, device, data):
        """Set data for a device of any type."""
        data.type = device.type
        data.name = device.name
        data.path = device.path
        data.size = device.size.get_bytes()
        data.parents = [d.name for d in device.parents]
        data.children = [d.name for d in device.children]
        data.is_disk = device.is_disk
        data.protected = device.protected
        data.removable = device.removable

        # FIXME: We should generate the description from the device data.
        data.description = getattr(device, "description", "")

        data.attrs["serial"] = self._get_attribute(device, "serial")
        data.attrs["vendor"] = self._get_attribute(device, "vendor")
        data.attrs["model"] = self._get_attribute(device, "model")
        data.attrs["bus"] = self._get_attribute(device, "bus")
        data.attrs["wwn"] = self._get_attribute(device, "wwn")
        data.attrs["uuid"] = self._get_attribute(device, "uuid")

    def _set_device_data_dasd(self, device, data):
        """Set data for a DASD device."""
        data.attrs["bus-id"] = self._get_attribute(device, "busid")

    def _set_device_data_fcoe(self, device, data):
        """Set data for an FCoE device."""
        data.attrs["path-id"] = self._get_attribute(device, "id_path")

    def _set_device_data_iscsi(self, device, data):
        """Set data for an iSCSI device."""
        data.attrs["port"] = self._get_attribute(device, "port")
        data.attrs["initiator"] = self._get_attribute(device, "initiator")
        data.attrs["lun"] = self._get_attribute(device, "lun")
        data.attrs["target"] = self._get_attribute(device, "target")
        data.attrs["path-id"] = self._get_attribute(device, "id_path")

    def _set_device_data_zfcp(self, device, data):
        """Set data for a ZFCP device."""
        data.attrs["fcp-lun"] = self._get_attribute(device, "fcp_lun")
        data.attrs["wwpn"] = self._get_attribute(device, "wwpn")
        data.attrs["hba-id"] = self._get_attribute(device, "hba_id")

    def get_format_data(self, device_name):
        """Get the device format data.

        Return data about a format of the specified device.

        For example: sda1

        :param device_name: a name of the device
        :return: an instance of DeviceFormatData
        """
        device = self._get_device(device_name)
        return self._get_format_data(device.format)

    def _get_format_data(self, fmt):
        """Get the format data.

        Retrieve data about a device format from
        the given format instance.

        :param fmt: an instance of DeviceFormat
        :return: an instance of DeviceFormatData
        """
        # Collect the format data.
        data = DeviceFormatData()
        data.type = fmt.type or ""
        data.mountable = fmt.mountable
        data.formattable = fmt.formattable
        data.description = fmt.name or ""

        # Collect the additional attributes.
        data.attrs["has_key"] = self._get_attribute(fmt, "has_key")
        data.attrs["uuid"] = self._get_attribute(fmt, "uuid")
        data.attrs["label"] = self._get_attribute(fmt, "label")
        data.attrs["mount-point"] = self._get_attribute(fmt, "mountpoint")

        # Prune the attributes.
        data.attrs = self._prune_attributes(data.attrs)
        return data

    def get_format_type_data(self, format_name):
        """Get the format type data.

        Return data about the specified format type.

        For example: ext4

        :param format_name: a name of the format type
        :return: an instance of DeviceFormatData
        """
        fmt = get_format(format_name)
        return self._get_format_type_data(fmt)

    def _get_format_type_data(self, fmt):
        """Get the format type data.

        Retrieve data about a format type from
        the given format instance.

        :param fmt: an instance of DeviceFormat
        :return: an instance of DeviceFormatData
        """
        data = DeviceFormatData()
        data.type = fmt.type or ""
        data.mountable = fmt.mountable
        data.description = fmt.name or ""
        return data

    def _get_device(self, name):
        """Find a device by its name.

        :param name: a name of the device
        :return: an instance of the Blivet's device
        :raise: UnknownDeviceError if no device is found
        """
        device = self.storage.devicetree.get_device_by_name(
            name, hidden=True, incomplete=True
        )

        if not device:
            raise UnknownDeviceError(name)

        return device

    def _get_devices(self, names):
        """Find devices by their names.

        :param names: names of the devices
        :return: a list of instances of the Blivet's device
        """
        return list(map(self._get_device, names))

    def _get_attribute(self, obj, name):
        """Get the attribute of the given object.

        If the attribute doesn't exist or it is not set,
        return None. Otherwise, return a string representation
        of the attribute value.

        :param obj: an object
        :param name: an attribute name
        :return: a string or None
        """
        try:
            value = getattr(obj, name)
        except AttributeError:
            # Skip if the attribute doesn't exist.
            return None

        if value in (None, ""):
            # Skip it the attribute is not set.
            return None

        return str(value)

    def _prune_attributes(self, attrs):
        """Prune the unset values of attributes.

        :param attrs: a dictionary of attributes
        :return: a pruned dictionary of attributes
        """
        return {k: v for k, v in attrs.items() if v is not None}

    def get_actions(self):
        """Get the device actions.

        The actions are pruned and sorted.

        :return: a list of DeviceActionData
        """
        actions = []

        self.storage.devicetree.actions.prune()
        self.storage.devicetree.actions.sort()

        for action in self.storage.devicetree.actions.find():
            actions.append(self._get_action_data(action))

        return actions

    def _get_action_data(self, action):
        """Get the action data.

        :param action: an instance of DeviceAction
        :return: an instance of DeviceActionData
        """
        data = DeviceActionData()

        # Collect the action data.
        data.action_type = action.type_string.lower()
        data.action_description = action.type_desc

        # Collect the object data.
        data.object_type = action.object_string.lower()
        data.object_description = action.object_type_string

        # Collect the device data.
        device = action.device
        data.device_name = device.name

        if action.is_create or action.is_device or action.is_format:
            data.attrs["mount-point"] = self._get_attribute(action.format, "mountpoint")

        if getattr(device, "description", ""):
            data.attrs["serial"] = self._get_attribute(device, "serial")
            data.device_description = _("{device_description} ({device_name})").format(
                device_description=device.description,
                device_name=device.name
            )
        elif getattr(device, "disk", None):
            data.attrs["serial"] = self._get_attribute(device.disk, "serial")
            data.device_description = _("{device_name} on {container_name}").format(
                device_name=device.name,
                container_name=device.disk.description
            )
        else:
            data.attrs["serial"] = self._get_attribute(device, "serial")
            data.device_description = device.name

        # Prune the attributes.
        data.attrs = self._prune_attributes(data.attrs)
        return data

    def resolve_device(self, dev_spec):
        """Get the device matching the provided device specification.

        The spec can be anything from a device name (eg: 'sda3') to a
        device node path (eg: '/dev/mapper/fedora-root') to something
        like 'UUID=xyz-tuv-qrs' or 'LABEL=rootfs'.

        If no device is found, return an empty string.

        :param dev_spec: a string describing a block device
        :return: a device name or an empty string
        """
        device = self.storage.devicetree.resolve_device(dev_spec)

        if not device:
            return ""

        return device.name

    def get_ancestors(self, device_names):
        """Collect ancestors of the specified devices.

        Ancestors of a device don't include the device itself.
        The list is sorted by names of the devices.

        :param device_names: a list of device names
        :return: a list of device names
        """
        devices = self._get_devices(device_names)
        ancestors = set()

        for device in devices:
            for ancestor in device.ancestors:
                if ancestor != device:
                    ancestors.add(ancestor.name)

        return sorted(ancestors)

    def get_supported_file_systems(self):
        """Get the supported types of filesystems.

        :return: a list of filesystem names
        """
        return get_supported_filesystems()

    def get_required_device_size(self, required_space):
        """Get device size we need to get the required space on the device.

        :param int required_space: a required space in bytes
        :return int: a required device size in bytes
        """
        return get_required_device_size(Size(required_space)).get_bytes()

    def get_file_system_free_space(self, mount_points):
        """Get total file system free space on the given mount points.

        :param mount_points: a list of mount points
        :return: a total size in bytes
        """
        return self.storage.get_file_system_free_space(mount_points).get_bytes()

    def get_disk_free_space(self, disk_names):
        """Get total free space on the given disks.

        Calculates free space available for use.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        disks = self._get_devices(disk_names)
        return self.storage.get_disk_free_space(disks).get_bytes()

    def get_disk_reclaimable_space(self, disk_names):
        """Get total reclaimable space on the given disks.

        Calculates free space unavailable but reclaimable
        from existing partitions.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        disks = self._get_devices(disk_names)
        return self.storage.get_disk_reclaimable_space(disks).get_bytes()

    def get_disk_total_space(self, disk_names):
        """Get total space on the given disks.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        disks = self._get_devices(disk_names)
        return sum((d.size for d in disks), Size(0)).get_bytes()

    def get_fstab_spec(self, name):
        """Get the device specifier for use in /etc/fstab.

        :param name: a name of the device
        :return: a device specifier for /etc/fstab
        """
        device = self._get_device(name)
        return device.fstab_spec

    def get_existing_systems(self):
        """Get existing GNU/Linux installations.

        :return: a list of data about found installations
        """
        return list(map(self._get_os_data, self.storage.roots))

    def _get_os_data(self, root):
        """Get the OS data.

        :param root: an instance of Root
        :return: an instance of OSData
        """
        data = OSData()
        data.os_name = root.name or ""
        data.devices = [
            device.name for device in root.devices
        ]
        data.mount_points = {
            path: device.name for path, device in root.mounts.items()
        }
        return data

    def _get_mount_point_constraints_data(self, spec):
        """Get the mount point data.

        :param spec: an instance of PartSpec
        :return: an instance of MountPointConstraintsData
        """
        data = MountPointConstraintsData()
        data.mount_point = spec.mountpoint or ""
        data.required_filesystem_type = spec.fstype or ""
        data.encryption_allowed = spec.encrypted
        data.logical_volume_allowed = spec.lv

        return data

    def get_mount_point_constraints(self):
        """Get list of constraints on mountpoints for the current platform

        Also provides hints if the partition is required or recommended.

        This includes mount points required to boot (e.g. /boot/efi, /boot)
        and the / partition which is always considered to be required.

        /boot is not required in general but can be required in some cases,
        depending on the filesystem on the root partition (ie crypted root).

        :return: a list of mount points with its constraints
        """

        constraints = []

        # Root partition is required
        root_partition = PartSpec(mountpoint="/", lv=True, thin=True, encrypted=True)
        root_constraint = self._get_mount_point_constraints_data(root_partition)
        root_constraint.required = True
        constraints.append(root_constraint)

        # Platform partitions are required except for /boot partiotion which is recommended
        for p in platform.partitions:
            if p.mountpoint:
                constraint = self._get_mount_point_constraints_data(p)
                if p.mountpoint == "/boot":
                    constraint.recommended = True
                else:
                    constraint.required = True
                constraints.append(constraint)

        return constraints

    def _get_platform_mount_point_data(self, spec):
        """Get the mount point data.

        :param spec: an instance of PartSpec
        :return: an instance of MountPointConstraintsData
        """
        data = MountPointConstraintsData()
        data.mount_point = spec.mountpoint or ""
        data.required_filesystem_type = spec.fstype or ""
        data.encryption_allowed = spec.encrypted
        data.logical_volume_allowed = spec.lv

        return data

    def get_required_mount_points(self):
        """Get list of required mount points for the current platform

        This includes mount points required to boot (e.g. /boot and /boot/efi)
        and the / partition which is always considered to be required.

        :return: a list of mount points with its constraints
        """
        root_partition = PartSpec(mountpoint="/", lv=True, thin=True, encrypted=True)
        ret = list(map(self._get_platform_mount_point_data,
                       [p for p in platform.partitions if p.mountpoint] + [root_partition]))
        return ret
