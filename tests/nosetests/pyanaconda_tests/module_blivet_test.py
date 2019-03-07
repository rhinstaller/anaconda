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
import sys
import pickle
import unittest
from unittest.mock import patch, Mock

from blivetgui.communication.proxy_utils import ProxyID

from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.partitioning import BlivetPartitioningModule
from pyanaconda.modules.storage.partitioning.blivet_interface import \
    BlivetPartitioningInterface
from pyanaconda.modules.storage.partitioning.configure import StorageConfigureTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.partitioning.base_execution import InteractivePartitioningExecutor


class BlivetPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the Blivet partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = BlivetPartitioningModule()
        self.interface = BlivetPartitioningInterface(self.module)

    @patch.dict('sys.modules')
    def unsupported_partitioning_test(self):
        """Test the UnsupportedPartitioningError."""
        # Forget imported modules from pyanaconda and blivetgui.
        for name in list(sys.modules):
            if name.startswith('pyanaconda') or name.startswith('blivetgui'):
                sys.modules.pop(name)

        # Disable the blivetgui package.
        sys.modules['blivetgui'] = None

        # Import the StorageModule again.
        from pyanaconda.modules.storage.storage import StorageModule

        # We should be able to create the Storage module
        storage_module = StorageModule()
        self.assertIsNotNone(storage_module.storage)

        # We should be able to access the Blivet module.
        blivet_module = storage_module._blivet_part_module
        self.assertIsNotNone(blivet_module.storage)

        # Import the exception again.
        from pyanaconda.modules.common.errors.storage import UnsupportedPartitioningError

        # Handle the missing support.
        with self.assertRaises(UnsupportedPartitioningError):
            self.assertFalse(blivet_module.storage_handler)

        with self.assertRaises(UnsupportedPartitioningError):
            self.assertFalse(blivet_module.request_handler)

        with self.assertRaises(UnsupportedPartitioningError):
            request = pickle.dumps(("call", "get_disks", []))
            blivet_module.send_request(request)

    def storage_handler_test(self):
        """Test the storage_handler property."""
        self.module.on_storage_reset(Mock())
        self.assertIsNotNone(self.module.storage_handler)
        self.assertEqual(self.module.storage, self.module.storage_handler.storage)

    def request_handler_test(self):
        """Test the request_handler property."""
        self.module.on_storage_reset(Mock())
        self.assertIsNotNone(self.module.request_handler)
        self.assertEqual(self.module.storage_handler, self.module.request_handler.blivet_utils)

    def send_request_test(self):
        """Test SendRequest."""
        self.module.on_storage_reset(Mock())
        request = pickle.dumps(("call", "get_disks", []))

        answer = self.interface.SendRequest(request)
        answer = pickle.loads(answer)

        self.assertIsInstance(answer, ProxyID)
        self.assertEqual(answer.id, 0)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageConfigureTask)
        self.assertIsInstance(obj.implementation._partitioning, InteractivePartitioningExecutor)
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
