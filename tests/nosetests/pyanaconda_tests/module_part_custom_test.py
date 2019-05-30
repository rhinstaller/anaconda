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
from unittest.mock import Mock, patch

from pyanaconda.modules.common.errors.storage import UnavailableDataError
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.partitioning import CustomPartitioningModule
from pyanaconda.modules.storage.partitioning.custom_interface import CustomPartitioningInterface
from pyanaconda.modules.storage.partitioning.custom_partitioning import CustomPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.storage import StorageModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class CustomPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the custom partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = CustomPartitioningModule()
        self.interface = CustomPartitioningInterface(self.module)

    def data_test(self, ):
        """Test the data property."""
        with self.assertRaises(UnavailableDataError):
            if self.module.data:
                self.fail("The data should not be available.")

        data = Mock()
        self.module.process_kickstart(data)
        self.assertEqual(self.module.data, data)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        self.module.process_kickstart(Mock())
        task_path = self.interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, CustomPartitioningTask)
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


class CustomPartitioningKickstartTestCase(unittest.TestCase):
    """Test the custom partitioning module with kickstart."""

    def setUp(self):
        """Set up the module."""
        self.storage_module = StorageModule()
        self.storage_interface = StorageInterface(self.storage_module)

        self.module = self.storage_module._custom_part_module
        self.interface = CustomPartitioningInterface(self.module)

    def _process_kickstart(self, ks_in):
        check_kickstart_interface(self, self.storage_interface, ks_in)

    def requires_passphrase_test(self):
        """Test RequiresPassphrase."""
        self._process_kickstart("part /")
        self.assertEqual(self.interface.RequiresPassphrase(), False)
        self._process_kickstart("part / --encrypted")
        self.assertEqual(self.interface.RequiresPassphrase(), True)
        self.interface.SetPassphrase("123456")
        self.assertEqual(self.interface.RequiresPassphrase(), False)
