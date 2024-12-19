#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from unittest.mock import Mock

from blivet.devices import DiskDevice, StorageDevice
from blivet.formats import get_format
from blivet.size import Size
from dasbus.typing import Bool, Str, get_variant

from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.structures.partitioning import MountPointRequest
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.partitioning.manual.manual_interface import (
    ManualPartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.manual.manual_module import (
    ManualPartitioningModule,
)
from pyanaconda.modules.storage.partitioning.manual.manual_partitioning import (
    ManualPartitioningTask,
)
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_task_creation,
    patch_dbus_publish_object,
)


class ManualPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the manual partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = ManualPartitioningModule()
        self.interface = ManualPartitioningInterface(self.module)

    def test_publication(self):
        """Test the DBus representation."""
        assert isinstance(self.module.for_publication(), ManualPartitioningInterface)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            MANUAL_PARTITIONING,
            self.interface,
            *args, **kwargs
        )

    def test_mount_points_property(self):
        """Test the mount points property."""
        self._check_dbus_property(
            "Requests",
            []
        )

        request = {
            "mount-point": get_variant(Str, "/boot"),
            "device-spec": get_variant(Str, "/dev/sda1"),
            "reformat": get_variant(Bool, False),
            "format-type": get_variant(Str, ""),
            "format-options": get_variant(Str, ""),
            "ks-spec": get_variant(Str, ""),
            "mount-options": get_variant(Str, "")
        }
        self._check_dbus_property(
            "Requests",
            [request]
        )

        request = {
            "mount-point": get_variant(Str, "/boot"),
            "device-spec": get_variant(Str, "/dev/sda1"),
            "reformat": get_variant(Bool, True),
            "format-type": get_variant(Str, "xfs"),
            "format-options": get_variant(Str, "-L BOOT"),
            "ks-spec": get_variant(Str, ""),
            "mount-options": get_variant(Str, "user")
        }
        self._check_dbus_property(
            "Requests",
            [request]
        )

        request_1 = {
            "mount-point": get_variant(Str, "/boot"),
            "device-spec": get_variant(Str, "/dev/sda1"),
            "reformat": get_variant(Bool, False),
            "format-type": get_variant(Str, ""),
            "format-options": get_variant(Str, ""),
            "ks-spec": get_variant(Str, ""),
            "mount-options": get_variant(Str, "")
        }
        request_2 = {
            "mount-point": get_variant(Str, "/"),
            "device-spec": get_variant(Str, "/dev/sda2"),
            "reformat": get_variant(Bool, True),
            "format-type": get_variant(Str, ""),
            "format-options": get_variant(Str, ""),
            "ks-spec": get_variant(Str, ""),
            "mount-options": get_variant(Str, "")
        }
        self._check_dbus_property(
            "Requests",
            [request_1, request_2]
        )

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.module.storage.devicetree._add_device(device)

    def test_gather_no_requests(self):
        """Test GatherRequests with no devices."""
        self.module.on_storage_changed(create_storage())
        assert self.interface.GatherRequests() == []

    def test_gather_unusable_requests(self):
        """Test GatherRequests with unusable devices."""
        self.module.on_storage_changed(create_storage())

        # Add device with no size.
        self._add_device(StorageDevice(
            "dev1",
            size=Size(0)
        ))

        assert self.interface.GatherRequests() == []

        # Add protected device.
        device = StorageDevice(
            "dev2",
            size=Size("1 GiB")
        )

        device.protected = True
        self._add_device(device)
        assert self.interface.GatherRequests() == []

        # Add unselected disk.
        self._add_device(DiskDevice(
            "dev3",
            size=Size("1 GiB")
        ))

        self.module.on_selected_disks_changed(["dev1", "dev2"])
        assert self.interface.GatherRequests() == []

    def test_gather_requests(self):
        """Test GatherRequests."""
        self.module.on_storage_changed(create_storage())

        self._add_device(StorageDevice(
            "dev1",
            size=Size("1 GiB"),
            fmt=get_format("ext4", mountpoint="/"))
        )

        self._add_device(StorageDevice(
            "dev2",
            size=Size("1 GiB"),
            fmt=get_format("swap"))
        )

        assert self.interface.GatherRequests() == [
            {
                'device-spec': get_variant(Str, 'dev1'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'ext4'),
                'mount-options': get_variant(Str, ''),
                'ks-spec': get_variant(Str, ''),
                'mount-point': get_variant(Str, '/'),
                'reformat': get_variant(Bool, False)
            },
            {
                'device-spec': get_variant(Str, 'dev2'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'swap'),
                'mount-options': get_variant(Str, ''),
                'ks-spec': get_variant(Str, ''),
                'mount-point': get_variant(Str, ''),
                'reformat': get_variant(Bool, False)
            }
        ]

    def test_gather_requests_combination(self):
        """Test GatherRequests with user requests."""
        self.module.on_storage_changed(create_storage())

        # Add devices dev1 and dev2.
        self._add_device(StorageDevice(
            "dev1",
            size=Size("1 GiB"),
            fmt=get_format("ext4", mountpoint="/"))
        )

        self._add_device(StorageDevice(
            "dev2",
            size=Size("1 GiB"),
            fmt=get_format("swap"))
        )

        # Add requests for dev1 and dev3.
        req1 = MountPointRequest()
        req1.device_spec = 'dev1'
        req1.format_options = '-L BOOT'
        req1.format_type = 'xfs'
        req1.mount_options = 'user'
        req1.mount_point = '/home'
        req1.reformat = True

        req3 = MountPointRequest()
        req3.device_spec = 'dev3'
        req3.mount_point = '/'

        self.module.set_requests([req1, req3])

        # Get requests for dev1 and dev2.
        assert self.interface.GatherRequests() == [
            {
                'device-spec': get_variant(Str, 'dev1'),
                'format-options': get_variant(Str, '-L BOOT'),
                'format-type': get_variant(Str, 'xfs'),
                'ks-spec': get_variant(Str, ''),
                'mount-options': get_variant(Str, 'user'),
                'mount-point': get_variant(Str, '/home'),
                'reformat': get_variant(Bool, True)
            },
            {
                'device-spec': get_variant(Str, 'dev2'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'swap'),
                'ks-spec': get_variant(Str, ''),
                'mount-options': get_variant(Str, ''),
                'mount-point': get_variant(Str, ''),
                'reformat': get_variant(Bool, False)
            }
        ]

    @patch_dbus_publish_object
    def test_configure_with_task(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(task_path, publisher, ManualPartitioningTask)

        assert obj.implementation._storage == self.module.storage
        assert obj.implementation._requests == self.module.requests
