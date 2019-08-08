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

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_task_creation

from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.formats.luks import LUKS2PBKDFArgs
from pykickstart.constants import AUTOPART_TYPE_LVM_THINP

from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning import AutoPartitioningModule
from pyanaconda.modules.storage.partitioning.automatic_interface import AutoPartitioningInterface
from pyanaconda.modules.storage.partitioning.automatic_partitioning import \
    AutomaticPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.storage.initialization import create_storage


class AutopartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the auto partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = AutoPartitioningModule()
        self.interface = AutoPartitioningInterface(self.module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            AUTO_PARTITIONING,
            self.interface,
            *args, **kwargs
        )

    def enabled_property_test(self):
        """Test the property enabled."""
        self._test_dbus_property(
            "Enabled",
            True
        )

    def request_property_test(self):
        """Test the property request."""
        in_value = {
            'partitioning-scheme': AUTOPART_TYPE_LVM_THINP,
            'file-system-type': 'ext4',
            'excluded-mount-points': ['/home', '/boot', 'swap'],
            'encrypted': True,
            'passphrase': '123456',
            'cipher': 'aes-xts-plain64',
            'luks-version': 'luks1',
            'pbkdf': 'argon2i',
            'pbkdf-memory': 256,
            'pbkdf-time': 100,
            'pbkdf-iterations': 1000,
            'escrow-certificate': 'file:///tmp/escrow.crt',
            'backup-passphrase-enabled': True,
        }

        out_value = {
            'partitioning-scheme': get_variant(Int, AUTOPART_TYPE_LVM_THINP),
            'file-system-type': get_variant(Str, 'ext4'),
            'excluded-mount-points': get_variant(List[Str], ['/home', '/boot', 'swap']),
            'encrypted': get_variant(Bool, True),
            'passphrase': get_variant(Str, '123456'),
            'cipher': get_variant(Str, 'aes-xts-plain64'),
            'luks-version': get_variant(Str, 'luks1'),
            'pbkdf': get_variant(Str, 'argon2i'),
            'pbkdf-memory': get_variant(Int, 256),
            'pbkdf-time': get_variant(Int, 100),
            'pbkdf-iterations': get_variant(Int, 1000),
            'escrow-certificate': get_variant(Str, 'file:///tmp/escrow.crt'),
            'backup-passphrase-enabled': get_variant(Bool, True),
        }

        self._test_dbus_property(
            "Request",
            in_value,
            out_value
        )

    def requires_passphrase_test(self):
        """Test RequiresPassphrase."""
        self.assertEqual(self.interface.RequiresPassphrase(), False)

        self.module.request.encrypted = True
        self.assertEqual(self.interface.RequiresPassphrase(), True)

        self.module.request.passphrase = "123456"
        self.assertEqual(self.interface.RequiresPassphrase(), False)

    def reset_test(self):
        """Test the reset of the storage."""
        with self.assertRaises(UnavailableStorageError):
            if self.module.storage:
                self.fail("The storage shouldn't be available.")

        storage = Mock()
        self.module.on_storage_reset(storage)

        self.assertEqual(self.module._current_storage, storage)
        self.assertIsNone(self.module._storage_playground)

        self.assertNotEqual(self.module.storage, storage)
        self.assertIsNotNone(self.module._storage_playground)

    @patch_dbus_publish_object
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(self, task_path, publisher, AutomaticPartitioningTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)
        self.assertEqual(obj.implementation._request, self.module.request)

    @patch_dbus_publish_object
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ValidateWithTask()

        obj = check_task_creation(self, task_path, publisher, StorageValidateTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)


class AutomaticPartitioningTaskTestCase(unittest.TestCase):
    """Test the automatic partitioning task."""

    def no_luks_format_args_test(self):
        storage = create_storage()
        request = PartitioningRequest()

        args = AutomaticPartitioningTask._get_luks_format_args(storage, request)
        self.assertEqual(args, {})

    def luks1_format_args_test(self):
        storage = create_storage()
        storage._escrow_certificates["file:///tmp/escrow.crt"] = "CERTIFICATE"

        request = PartitioningRequest()
        request.encrypted = True
        request.passphrase = "passphrase"
        request.luks_version = "luks1"
        request.cipher = "aes-xts-plain64"
        request.escrow_certificate = "file:///tmp/escrow.crt"
        request.backup_passphrase_enabled = True

        args = AutomaticPartitioningTask._get_luks_format_args(storage, request)
        self.assertEqual(args, {
            "passphrase": "passphrase",
            "cipher": "aes-xts-plain64",
            "luks_version": "luks1",
            "pbkdf_args": None,
            "escrow_cert": "CERTIFICATE",
            "add_backup_passphrase": True,
            "min_luks_entropy": MIN_CREATE_ENTROPY,
        })

    def luks2_format_args_test(self):
        storage = create_storage()
        request = PartitioningRequest()
        request.encrypted = True
        request.passphrase = "default"
        request.luks_version = "luks2"
        request.pbkdf = "argon2i"
        request.pbkdf_memory = 256
        request.pbkdf_iterations = 1000
        request.pbkdf_time = 100

        args = AutomaticPartitioningTask._get_luks_format_args(storage, request)
        pbkdf_args = args.pop("pbkdf_args")

        self.assertEqual(args, {
            "passphrase": "default",
            "cipher": "",
            "luks_version": "luks2",
            "escrow_cert": None,
            "add_backup_passphrase": False,
            "min_luks_entropy": MIN_CREATE_ENTROPY,
        })

        self.assertIsInstance(pbkdf_args, LUKS2PBKDFArgs)
        self.assertEqual(pbkdf_args.type, "argon2i")
        self.assertEqual(pbkdf_args.max_memory_kb, 256)
        self.assertEqual(pbkdf_args.iterations, 1000)
        self.assertEqual(pbkdf_args.time_ms, 100)
