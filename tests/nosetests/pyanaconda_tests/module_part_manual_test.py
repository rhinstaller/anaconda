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
from unittest.mock import patch, Mock

from pyanaconda.dbus.typing import get_variant, Str, Bool
from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.partitioning import ManualPartitioningModule
from pyanaconda.modules.storage.partitioning.manual_interface import ManualPartitioningInterface
from pyanaconda.modules.storage.partitioning.manual_partitioning import ManualPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from tests.nosetests.pyanaconda_tests import check_dbus_property


class ManualPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the manual partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = ManualPartitioningModule()
        self.interface = ManualPartitioningInterface(self.module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            MANUAL_PARTITIONING,
            self.interface,
            *args, **kwargs
        )

    def enabled_property_test(self):
        """Test the enabled property."""
        self._test_dbus_property(
            "Enabled",
            True
        )

        self._test_dbus_property(
            "Enabled",
            False
        )

    def mount_points_property_test(self):
        """Test the mount points property."""
        self._test_dbus_property(
            "Requests",
            []
        )

        in_value = [
            {
                "mount-point": "/boot",
                "device-spec": "/dev/sda1"
            }
        ]

        out_value = [
            {
                "mount-point": get_variant(Str, "/boot"),
                "device-spec": get_variant(Str, "/dev/sda1"),
                "reformat": get_variant(Bool, False),
                "format-type": get_variant(Str, ""),
                "format-options": get_variant(Str, ""),
                "mount-options": get_variant(Str, "")
            }
        ]

        self._test_dbus_property(
            "Requests",
            in_value,
            out_value
        )

        in_value = [
            {
                "mount-point":  "/boot",
                "device-spec": "/dev/sda1",
                "reformat": True,
                "format-type": "xfs",
                "format-options": "-L BOOT",
                "mount-options": "user"
            }
        ]

        out_value = [
            {
                "mount-point": get_variant(Str, "/boot"),
                "device-spec": get_variant(Str, "/dev/sda1"),
                "reformat": get_variant(Bool, True),
                "format-type": get_variant(Str, "xfs"),
                "format-options": get_variant(Str, "-L BOOT"),
                "mount-options": get_variant(Str, "user")
            }
        ]

        self._test_dbus_property(
            "Requests",
            in_value,
            out_value,
        )

        in_value = [
            {
                "mount-point": "/boot",
                "device-spec": "/dev/sda1"
            },
            {
                "mount-point": "/",
                "device-spec": "/dev/sda2",
                "reformat": True
            }
        ]

        out_value = [
            {
                "mount-point": get_variant(Str, "/boot"),
                "device-spec": get_variant(Str, "/dev/sda1"),
                "reformat": get_variant(Bool, False),
                "format-type": get_variant(Str, ""),
                "format-options": get_variant(Str, ""),
                "mount-options": get_variant(Str, "")
            },
            {
                "mount-point": get_variant(Str, "/"),
                "device-spec": get_variant(Str, "/dev/sda2"),
                "reformat": get_variant(Bool, True),
                "format-type": get_variant(Str, ""),
                "format-options": get_variant(Str, ""),
                "mount-options": get_variant(Str, "")
            }
        ]

        self._test_dbus_property(
            "Requests",
            in_value,
            out_value
        )

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, ManualPartitioningTask)
        self.assertEqual(obj.implementation._storage, self.module.storage)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ValidateWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageValidateTask)
        self.assertEqual(obj.implementation._storage, self.module.storage)
