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

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object

from tests.nosetests.pyanaconda_tests import check_task_creation, check_dbus_property

from blivet.devices import StorageDevice, DiskDevice
from blivet.formats import get_format
from blivet.size import Size

from dasbus.typing import get_variant, Str, Bool
from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.structures.partitioning import MountPointRequest
from pyanaconda.modules.storage.partitioning.manual.manual_module import ManualPartitioningModule
from pyanaconda.modules.storage.partitioning.manual.manual_interface import \
    ManualPartitioningInterface
from pyanaconda.modules.storage.partitioning.manual.manual_partitioning import \
    ManualPartitioningTask
from pyanaconda.modules.storage.devicetree import create_storage


class ManualPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the manual partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = ManualPartitioningModule()
        self.interface = ManualPartitioningInterface(self.module)

    def publication_test(self):
        """Test the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), ManualPartitioningInterface)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            MANUAL_PARTITIONING,
            self.interface,
            *args, **kwargs
        )

    def mount_points_property_test(self):
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
            "mount-options": get_variant(Str, "")
        }
        request_2 = {
            "mount-point": get_variant(Str, "/"),
            "device-spec": get_variant(Str, "/dev/sda2"),
            "reformat": get_variant(Bool, True),
            "format-type": get_variant(Str, ""),
            "format-options": get_variant(Str, ""),
            "mount-options": get_variant(Str, "")
        }
        self._check_dbus_property(
            "Requests",
            [request_1, request_2]
        )

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.module.storage.devicetree._add_device(device)

    def gather_no_requests_test(self):
        """Test GatherRequests with no devices."""
        self.module.on_storage_changed(create_storage())
        self.assertEqual(self.interface.GatherRequests(), [])

    def gather_unusable_requests_test(self):
        """Test GatherRequests with unusable devices."""
        self.module.on_storage_changed(create_storage())

        # Add device with no size.
        self._add_device(StorageDevice(
            "dev1",
            size=Size(0)
        ))

        self.assertEqual(self.interface.GatherRequests(), [])

        # Add protected device.
        device = StorageDevice(
            "dev2",
            size=Size("1 GiB")
        )

        device.protected = True
        self._add_device(device)
        self.assertEqual(self.interface.GatherRequests(), [])

        # Add unselected disk.
        self._add_device(DiskDevice(
            "dev3",
            size=Size("1 GiB")
        ))

        self.module.on_selected_disks_changed(["dev1", "dev2"])
        self.assertEqual(self.interface.GatherRequests(), [])

    def gather_requests_test(self):
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

        self.assertEqual(self.interface.GatherRequests(), [
            {
                'device-spec': get_variant(Str, '/dev/dev1'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'ext4'),
                'mount-options': get_variant(Str, ''),
                'mount-point': get_variant(Str, '/'),
                'reformat': get_variant(Bool, False)
            },
            {
                'device-spec': get_variant(Str, '/dev/dev2'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'swap'),
                'mount-options': get_variant(Str, ''),
                'mount-point': get_variant(Str, ''),
                'reformat': get_variant(Bool, False)
            }
        ])

    def gather_requests_combination_test(self):
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
        req1.device_spec = '/dev/dev1'
        req1.format_options = '-L BOOT'
        req1.format_type = 'xfs'
        req1.mount_options = 'user'
        req1.mount_point = '/home'
        req1.reformat = True

        req3 = MountPointRequest()
        req3.device_spec = '/dev/dev3'
        req3.mount_point = '/'

        self.module.set_requests([req1, req3])

        # Get requests for dev1 and dev2.
        self.assertEqual(self.interface.GatherRequests(), [
            {
                'device-spec': get_variant(Str, '/dev/dev1'),
                'format-options': get_variant(Str, '-L BOOT'),
                'format-type': get_variant(Str, 'xfs'),
                'mount-options': get_variant(Str, 'user'),
                'mount-point': get_variant(Str, '/home'),
                'reformat': get_variant(Bool, True)
            },
            {
                'device-spec': get_variant(Str, '/dev/dev2'),
                'format-options': get_variant(Str, ''),
                'format-type': get_variant(Str, 'swap'),
                'mount-options': get_variant(Str, ''),
                'mount-point': get_variant(Str, ''),
                'reformat': get_variant(Bool, False)
            }
        ])

    @patch_dbus_publish_object
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(self, task_path, publisher, ManualPartitioningTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)
        self.assertEqual(obj.implementation._requests, self.module.requests)
