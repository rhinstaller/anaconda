#
# DBus structures for the storage data.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["DeviceActionData", "DeviceData", "DeviceFormatData", "OSData"]


class DeviceData(DBusData):
    """Device data."""

    def __init__(self):
        self._device_id = ""
        self._type = ""
        self._name = ""
        self._path = ""
        self._size = 0
        self._parents = []
        self._children = []
        self._links = []
        self._is_disk = False
        self._protected = False
        self._removable = False
        self._attrs = {}
        self._description = ""

    @property
    def type(self) -> Str:
        """A type of the device.

        :return: a device type
        """
        return self._type

    @type.setter
    def type(self, value: Str):
        self._type = value

    @property
    def name(self) -> Str:
        """A name of the device

        :return: a device name
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def device_id(self) -> Str:
        """A ID of the device

        :return: a device ID
        """
        return self._device_id

    @device_id.setter
    def device_id(self, device_id: Str):
        self._device_id = device_id

    @property
    def path(self) -> Str:
        """A device node representing the device.

        :return: a path
        """
        return self._path

    @path.setter
    def path(self, value: Str):
        self._path = value

    @property
    def size(self) -> UInt64:
        """A size of the device

        :return: a size in bytes
        """
        return UInt64(self._size)

    @size.setter
    def size(self, size: UInt64):
        self._size = size

    @property
    def is_disk(self) -> Bool:
        """Is this device a disk?

        :return: True or False
        """
        return self._is_disk

    @is_disk.setter
    def is_disk(self, is_disk: Bool):
        self._is_disk = is_disk

    @property
    def protected(self) -> Bool:
        """Is this device protected?"""
        return self._protected

    @protected.setter
    def protected(self, value):
        self._protected = value

    @property
    def removable(self) -> Bool:
        """Is this device removable?"""
        return self._removable

    @removable.setter
    def removable(self, value: Bool):
        self._removable = value

    @property
    def parents(self) -> List[Str]:
        """Parents of the device.

        :return: a list of device IDs
        """
        return self._parents

    @parents.setter
    def parents(self, ids):
        self._parents = ids

    @property
    def children(self) -> List[Str]:
        """Children of the device.

        :return: a list of device IDs
        """
        return self._children

    @children.setter
    def children(self, value):
        self._children = value

    @property
    def links(self) -> List[Str]:
        """Symbolic links for the device.

        :return: a list of device paths
        """
        return self._links

    @links.setter
    def links(self, value):
        self._links = value

    @property
    def attrs(self) -> Dict[Str, Str]:
        """Additional attributes.

        The supported attributes are defined by
        the lists below.

        Attributes for all types:
            serial
            vendor
            model
            bus
            wwn
            uuid

        Attributes for DASD:
            bus-id

        Attributes for FCoE:
            path-id

        Attributes for iSCSI:
            port
            initiator
            lun
            target
            path-id

        Attributes for NVMe Fabrics:
            nsid
            eui64
            nguid
            controllers-id
            transports-type
            transports-address
            subsystems-nqn

        Attributes for ZFCP:
            fcp-lun
            wwpn
            hba-id
            path-id

        Attributes for partitions:
            partition-type-name

        :return: a dictionary of attributes
        """
        return self._attrs

    @attrs.setter
    def attrs(self, attrs: Dict[Str, Str]):
        self._attrs = attrs

    @property
    def description(self) -> Str:
        """Description of the device.

        FIXME: This is a temporary property.

        :return: a string with description
        """
        return self._description

    @description.setter
    def description(self, text):
        self._description = text


class DeviceFormatData(DBusData):
    """Device format data."""

    def __init__(self):
        self._type = ""
        self._mountable = False
        self._formattable = False
        self._attrs = {}
        self._description = ""

    @property
    def type(self) -> Str:
        """A type of the format.

        :return: a format type
        """
        return self._type

    @type.setter
    def type(self, value):
        self._type = value

    @property
    def mountable(self) -> Bool:
        """Is this something we can mount?"""
        return self._mountable

    @mountable.setter
    def mountable(self, value: Bool):
        self._mountable = value

    @property
    def formattable(self) -> Bool:
        """Is this something we can format?"""
        return self._formattable

    @formattable.setter
    def formattable(self, value: Bool):
        self._formattable = value

    @property
    def attrs(self) -> Dict[Str, Str]:
        """Additional attributes.

        The supported attributes are defined by
        the list below.

        Attributes for all types:
            uuid
            label

        Attributes for file systems:
            mount-point

        Attributes for LUKS:
            has_key

        :return: a dictionary of attributes
        """
        return self._attrs

    @attrs.setter
    def attrs(self, attrs: Dict[Str, Str]):
        self._attrs = attrs

    @property
    def description(self) -> Str:
        """Description of the format.

        FIXME: This is a temporary property.

        :return: a string with description
        """
        return self._description

    @description.setter
    def description(self, text):
        self._description = text


class DeviceActionData(DBusData):
    """Device action data."""

    def __init__(self):
        self._action_type = ""
        self._action_description = ""

        self._object_type = ""
        self._object_description = ""

        self._device_name = ""
        self._device_id = ""
        self._device_description = ""

        self._attrs = {}

    @property
    def action_type(self) -> Str:
        """A type of the action.

        For example:
            destroy, resize, create,
            add, remove, configure

        :return: a string with the type
        """
        return self._action_type

    @action_type.setter
    def action_type(self, name: Str):
        self._action_type = name

    @property
    def action_description(self) -> Str:
        """Description of the action.

        :return: a string with description
        """
        return self._action_description

    @action_description.setter
    def action_description(self, value):
        self._action_description = value

    @property
    def object_type(self) -> Str:
        """A type of the action object.

        For example:
            format, device, container

        :return: a string with the type
        """
        return self._object_type

    @object_type.setter
    def object_type(self, name: Str):
        self._object_type = name

    @property
    def object_description(self) -> Str:
        """Description of the action object.

        :return: a string with description
        """
        return self._object_description

    @object_description.setter
    def object_description(self, value):
        self._object_description = value

    @property
    def device_name(self) -> Str:
        """A name of the device.

        :return: a device name
        """
        return self._device_name

    @device_name.setter
    def device_name(self, name: Str):
        self._device_name = name

    @property
    def device_id(self) -> Str:
        """A ID of the device.

        :return: a device ID
        """
        return self._device_id

    @device_id.setter
    def device_id(self, device_id: Str):
        self._device_id = device_id

    @property
    def device_description(self) -> Str:
        """Description of the device.

        :return: a string with description
        """
        return self._device_description

    @device_description.setter
    def device_description(self, value):
        self._device_description = value

    @property
    def attrs(self) -> Dict[Str, Str]:
        """Additional attributes.

        The supported attributes are defined by
        the lists below.

        Attributes for all types:
            serial

        Attributes for file systems:
            mount-point

        :return: a dictionary of attributes
        """
        return self._attrs

    @attrs.setter
    def attrs(self, attrs: Dict[Str, Str]):
        self._attrs = attrs


class OSData(DBusData):
    """Data of an existing OS installation."""

    def __init__(self):
        self._os_name = ""
        self._devices = []
        self._mount_points = {}

    @property
    def os_name(self) -> Str:
        """Name of the OS.

        :return: a string with name
        """
        return self._os_name

    @os_name.setter
    def os_name(self, name: Str):
        self._os_name = name

    @property
    def devices(self) -> List[Str]:
        """Devices used by the OS.

        For example:

        * bootloader devices
        * mount point sources
        * swap devices

        :return: a list of device names
        """
        return self._devices

    @devices.setter
    def devices(self, devices: List[Str]):
        self._devices = devices

    @property
    def mount_points(self) -> Dict[Str, Str]:
        """Mount points defined by the OS.

        :return: a dictionary of mount points and device names
        """
        return self._mount_points

    @mount_points.setter
    def mount_points(self, mount_points: Dict[Str, Str]):
        self._mount_points = mount_points

    def get_root_device(self):
        """Get the root device.

        :return: a device name or None
        """
        return self.mount_points.get("/")


class MountPointConstraintsData(DBusData):
    """Constrains (filesystem and device types allowed) for mount points"""

    def __init__(self):
        self._mount_point = ""
        self._required_filesystem_type = ""
        self._encryption_allowed = False
        self._logical_volume_allowed = False
        self._required = False
        self._recommended = False

    @property
    def mount_point(self) -> Str:
        """Mount point value, e.g. /boot/efi

        :return: a string with mount point
        """
        return self._mount_point

    @mount_point.setter
    def mount_point(self, mount_point: Str):
        self._mount_point = mount_point

    @property
    def required_filesystem_type(self) -> Str:
        """Filesystem type required for mount point

        :return: a string with filesystem type required for this mount point
        """
        return self._required_filesystem_type

    @required_filesystem_type.setter
    def required_filesystem_type(self, required_filesystem_type: Str):
        self._required_filesystem_type = required_filesystem_type

    @property
    def encryption_allowed(self) -> Bool:
        """Whether this mount point can be encrypted or not

        :return: bool
        """
        return self._encryption_allowed

    @encryption_allowed.setter
    def encryption_allowed(self, encryption_allowed: Bool):
        self._encryption_allowed = encryption_allowed

    @property
    def logical_volume_allowed(self) -> Bool:
        """Whether this mount point can be a LVM logical volume or not

        :return: bool
        """
        return self._logical_volume_allowed

    @logical_volume_allowed.setter
    def logical_volume_allowed(self, logical_volume_allowed: Bool):
        self._logical_volume_allowed = logical_volume_allowed

    @property
    def required(self) -> Bool:
        """Whether this mount point is required

        :return: bool
        """
        return self._required

    @required.setter
    def required(self, required: Bool):
        self._required = required

    @property
    def recommended(self) -> Bool:
        """Whether this mount point is recommended

        :return: bool
        """
        return self._recommended

    @recommended.setter
    def recommended(self, recommended: Bool):
        self._recommended = recommended
