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

from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.formats.luks import LUKS2PBKDFArgs
from pykickstart.constants import AUTOPART_TYPE_LVM_THINP, AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_LVM

from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.partitioning import AutoPartitioningModule
from pyanaconda.modules.storage.partitioning.automatic_interface import AutoPartitioningInterface
from pyanaconda.modules.storage.partitioning.automatic_partitioning import \
    AutomaticPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.storage.initialization import create_storage
from tests.nosetests.pyanaconda_tests import check_dbus_property


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

    def type_property_test(self):
        """Test the type property."""
        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_LVM_THINP
        )

        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_PLAIN
        )

        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_LVM
        )

    def filesystem_type_property_test(self):
        """Test the filesystem property."""
        self._test_dbus_property(
            "FilesystemType",
            "ext4"
        )

    def nohome_property_test(self):
        """Test the nohome property."""
        def setter(value):
            self.module.set_nohome(value)
            self.module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoHome",
            True,
            setter=setter
        )

    def noboot_property_test(self):
        """Test the noboot property."""
        def setter(value):
            self.module.set_noboot(value)
            self.module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoBoot",
            True,
            setter=setter
        )

    def noswap_property_test(self):
        """Test the noswap property."""
        def setter(value):
            self.module.set_noswap(value)
            self.module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoSwap",
            True,
            setter=setter
        )

    def encrypted_property_test(self):
        """Test the encrypted property."""
        self._test_dbus_property(
            "Encrypted",
            True
        )

    def cipher_property_test(self):
        """Test the cipher property,"""
        self._test_dbus_property(
            "Cipher",
            "aes-xts-plain64"
        )

    def passphrase_property_test(self):
        """Test the passphrase property."""
        self._test_dbus_property(
            "Passphrase",
            "123456"
        )

    def requires_passphrase_test(self):
        """Test RequiresPassphrase."""
        self.assertEqual(self.interface.RequiresPassphrase(), False)
        self.interface.SetEncrypted(True)
        self.assertEqual(self.interface.RequiresPassphrase(), True)
        self.interface.SetPassphrase("123456")
        self.assertEqual(self.interface.RequiresPassphrase(), False)

    def luks_version_property_test(self):
        """Test the luks version property."""
        self._test_dbus_property(
            "LUKSVersion",
            "luks1"
        )

    def pbkdf_property_test(self):
        """Test the PBKDF property."""
        self._test_dbus_property(
            "PBKDF",
            "argon2i"
        )

    def pbkdf_memory_property_test(self):
        """Test the PBKDF memory property."""
        self._test_dbus_property(
            "PBKDFMemory",
            256
        )

    def pbkdf_time_property_test(self):
        """Test the PBKDF time property."""
        self._test_dbus_property(
            "PBKDFTime",
            100
        )

    def pbkdf_iterations_property_test(self):
        """Test the PBKDF iterations property."""
        self._test_dbus_property(
            "PBKDFIterations",
            1000
        )

    def escrowcert_property_test(self):
        """Test the escrowcert property."""
        self._test_dbus_property(
            "Escrowcert",
            "file:///tmp/escrow.crt"
        )

    def backup_passphrase_enabled_property_test(self):
        """Test the backup passphrase enabled property."""
        self._test_dbus_property(
            "BackupPassphraseEnabled",
            True
        )

    def pbkdf_args_test(self):
        """Test the pbkdf_args property."""
        self.module.set_encrypted(False)
        self.assertEqual(self.module.pbkdf_args, None)

        self.module.set_encrypted(True)
        self.module.set_luks_version("luks1")
        self.assertEqual(self.module.pbkdf_args, None)

        self.module.set_encrypted(True)
        self.module.set_luks_version("luks2")
        self.assertEqual(self.module.pbkdf_args, None)

        self.module.set_encrypted(True)
        self.module.set_luks_version("luks2")
        self.module.set_pbkdf("argon2i")
        self.module.set_pbkdf_memory(256)
        self.module.set_pbkdf_iterations(1000)
        self.module.set_pbkdf_time(100)

        pbkdf_args = self.module.pbkdf_args
        self.assertIsInstance(pbkdf_args, LUKS2PBKDFArgs)
        self.assertEqual(pbkdf_args.type, "argon2i")
        self.assertEqual(pbkdf_args.max_memory_kb, 256)
        self.assertEqual(pbkdf_args.iterations, 1000)
        self.assertEqual(pbkdf_args.time_ms, 100)

    def luks_format_args_test(self):
        """Test the luks_format_args property."""
        storage = create_storage()
        storage._escrow_certificates["file:///tmp/escrow.crt"] = "CERTIFICATE"
        self.module.on_storage_reset(storage)

        self.module.set_encrypted(False)
        self.assertEqual(self.module.luks_format_args, {})

        self.module.set_encrypted(True)
        self.module.set_passphrase("default")
        self.assertEqual(self.module.luks_format_args, {
            "passphrase": "default",
            "cipher": "",
            "luks_version": "luks2",
            "pbkdf_args": None,
            "escrow_cert": None,
            "add_backup_passphrase": False,
            "min_luks_entropy": MIN_CREATE_ENTROPY,
        })

        self.module.set_encrypted(True)
        self.module.set_luks_version("luks1")
        self.module.set_passphrase("passphrase")
        self.module.set_cipher("aes-xts-plain64")
        self.module.set_escrowcert("file:///tmp/escrow.crt")
        self.module.set_backup_passphrase_enabled(True)
        self.assertEqual(self.module.luks_format_args, {
            "passphrase": "passphrase",
            "cipher": "aes-xts-plain64",
            "luks_version": "luks1",
            "pbkdf_args": None,
            "escrow_cert": "CERTIFICATE",
            "add_backup_passphrase": True,
            "min_luks_entropy": MIN_CREATE_ENTROPY,
        })

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

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, AutomaticPartitioningTask)
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
