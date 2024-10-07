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
import pytest

from unittest.mock import Mock, patch, ANY, call

from blivet.formats.luks import LUKS2PBKDFArgs
from blivet.size import Size
from blivet.errors import StorageError

from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.storage.partitioning.automatic.resizable_module import \
    ResizableDeviceTreeModule
from pyanaconda.modules.storage.partitioning.automatic.utils import \
    get_disks_for_implicit_partitions
from pyanaconda.modules.storage.partitioning.specification import PartSpec
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_task_creation, check_dbus_object_creation

from pykickstart.constants import AUTOPART_TYPE_LVM_THINP, AUTOPART_TYPE_PLAIN, \
    AUTOPART_TYPE_LVM, AUTOPART_TYPE_BTRFS

from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning.automatic.automatic_module import \
    AutoPartitioningModule
from pyanaconda.modules.storage.partitioning.automatic.automatic_interface import \
    AutoPartitioningInterface
from pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning import \
    AutomaticPartitioningTask
from pyanaconda.modules.storage.partitioning.automatic.utils import get_default_partitioning
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.devicetree import create_storage


class AutopartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the auto partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = AutoPartitioningModule()
        self.interface = AutoPartitioningInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            AUTO_PARTITIONING,
            self.interface,
            *args, **kwargs
        )

    def test_publication(self):
        """Test the DBus representation."""
        assert isinstance(self.module.for_publication(), AutoPartitioningInterface)

    @patch_dbus_publish_object
    def test_device_tree(self, publisher):
        """Test the device tree."""
        self.module.on_storage_changed(Mock())
        path = self.interface.GetDeviceTree()
        obj = check_dbus_object_creation(path, publisher, ResizableDeviceTreeModule)
        assert obj.implementation.storage == self.module.storage

        self.module.on_partitioning_reset()
        assert obj.implementation.storage == self.module.storage

        self.module.on_storage_changed(Mock())
        assert obj.implementation.storage == self.module.storage

    def test_request_property(self):
        """Test the property request."""
        request = {
            'partitioning-scheme': get_variant(Int, AUTOPART_TYPE_LVM_THINP),
            'file-system-type': get_variant(Str, 'ext4'),
            'excluded-mount-points': get_variant(List[Str], ['/home', '/boot', 'swap']),
            'reformatted-mount-points': get_variant(List[Str], ['/']),
            'removed-mount-points': get_variant(List[Str], ['/boot', 'bootloader']),
            'reused-mount-points': get_variant(List[Str], ['/home']),
            'hibernation': get_variant(Bool, False),
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
            'opal-admin-passphrase': get_variant(Str, '123456'),
        }
        self._check_dbus_property(
            "Request",
            request
        )

    def test_requires_passphrase(self):
        """Test RequiresPassphrase."""
        assert self.interface.RequiresPassphrase() is False

        self.module.request.encrypted = True
        assert self.interface.RequiresPassphrase() is True

        self.module.request.passphrase = "123456"
        assert self.interface.RequiresPassphrase() is False

    def test_reset(self):
        """Test the reset of the storage."""
        with pytest.raises(UnavailableStorageError):
            if self.module.storage:
                self.fail("The storage shouldn't be available.")

        storage = Mock()
        self.module.on_storage_changed(storage)

        assert self.module._current_storage == storage
        assert self.module._storage_playground is None

        assert self.module.storage != storage
        assert self.module._storage_playground is not None

    @patch_dbus_publish_object
    def test_configure_with_task(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(task_path, publisher, AutomaticPartitioningTask)

        assert obj.implementation._storage == self.module.storage
        assert obj.implementation._request == self.module.request

    @patch_dbus_publish_object
    def test_validate_with_task(self, publisher):
        """Test ValidateWithTask."""
        self.module.on_storage_changed(Mock())
        task_path = self.interface.ValidateWithTask()

        obj = check_task_creation(task_path, publisher, StorageValidateTask)
        assert obj.implementation._storage == self.module.storage

        report = ValidationReport()
        report.error_messages = [
            "Something is wrong.",
            "Something is very wrong."
        ]
        report.warning_messages = [
            "Something might be wrong."
        ]
        obj.implementation._set_result(report)

        result = obj.GetResult()
        expected_result = get_variant(Structure, {
            "error-messages": get_variant(List[Str], [
                "Something is wrong.",
                "Something is very wrong."
            ]),
            "warning-messages": get_variant(List[Str], [
                "Something might be wrong."
            ])
        })

        assert isinstance(result, Variant)
        assert get_native(result) == get_native(expected_result)
        assert result.equal(expected_result)


class AutomaticPartitioningTaskTestCase(unittest.TestCase):
    """Test the automatic partitioning task."""

    def test_no_luks_format_args(self):
        storage = create_storage()
        request = PartitioningRequest()

        args = AutomaticPartitioningTask._get_luks_format_args(storage, request)
        assert args == {}

    def test_luks1_format_args(self):
        storage = create_storage()
        storage._escrow_certificates["file:///tmp/escrow.crt"] = "CERTIFICATE"

        request = PartitioningRequest()
        request.encrypted = True
        request.passphrase = "passphrase"
        request.luks_version = "luks1"
        request.cipher = "aes-xts-plain64"
        request.escrow_certificate = "file:///tmp/escrow.crt"
        request.backup_passphrase_enabled = True
        request.opal_admin_passphrase = "passphrase"

        args = AutomaticPartitioningTask._get_luks_format_args(storage, request)
        assert args == {
            "passphrase": "passphrase",
            "cipher": "aes-xts-plain64",
            "luks_version": "luks1",
            "pbkdf_args": None,
            "escrow_cert": "CERTIFICATE",
            "add_backup_passphrase": True,
            "opal_admin_passphrase": "passphrase",
        }

    def test_luks2_format_args(self):
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

        assert args == {
            "passphrase": "default",
            "cipher": "",
            "luks_version": "luks2",
            "escrow_cert": None,
            "add_backup_passphrase": False,
            "opal_admin_passphrase": "",
        }

        assert isinstance(pbkdf_args, LUKS2PBKDFArgs)
        assert pbkdf_args.type == "argon2i"
        assert pbkdf_args.max_memory_kb == 256
        assert pbkdf_args.iterations == 1000
        assert pbkdf_args.time_ms == 100

    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.platform')
    def test_get_default_partitioning(self, platform):
        platform.partitions = [PartSpec("/boot")]
        requests = get_default_partitioning()

        assert ["/boot", "/", "/home"] == [spec.mountpoint for spec in requests]

    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.suggest_swap_size')
    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.platform')
    def test_get_partitioning(self, platform, suggest_swap_size):
        storage = create_storage()

        # Set the platform specs.
        platform.partitions = [
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        ]

        # Set the file system type for /boot.
        storage._bootloader = Mock(stage2_format_types=["xfs"])

        # Set the swap size.
        suggest_swap_size.return_value = Size("1024MiB")

        # Collect the requests.
        partitioning_request = PartitioningRequest()
        partitioning_request._excluded_mount_points = ["/home", "/boot", "swap"]
        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert ["/"] == [spec.mountpoint for spec in requests]

        partitioning_request = PartitioningRequest()
        partitioning_request._excluded_mount_points = []
        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert ["/boot", "/", "/home"] == \
            [spec.mountpoint for spec in requests]
        assert ["xfs", "ext4", "ext4"] == \
            [spec.fstype for spec in requests]
        assert [Size("1GiB"), Size("1GiB"), Size("500MiB")] == \
            [spec.size for spec in requests]

    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.platform')
    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.conf')
    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.suggest_swap_size')
    def test_get_partitioning_hibernation(self, suggest_swap_size, mocked_config, platform):
        """Test the creation of swap with PartitioningRequest.hibernation."""
        swap_size = Size("1GiB")
        suggest_swap_size.return_value = swap_size

        storage = create_storage()
        platform.partitions = [
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        ]

        # Test Case: No swap, hibernation
        mocked_config.storage.default_partitioning = [
            {
                'name': '/',
                'size': Size("50 GiB"),
            },
        ]
        partitioning_request = PartitioningRequest()
        partitioning_request.hibernation = True

        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert any(spec for spec in requests if spec.fstype == "swap")
        assert list(spec.size for spec in requests if spec.fstype == "swap") == [swap_size]
        suggest_swap_size.assert_called_with(hibernation=True, disk_space=ANY)

        # Test Case: No swap, no hibernation
        partitioning_request = PartitioningRequest()
        partitioning_request.hibernation = False

        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert not any(spec for spec in requests if spec.fstype == "swap")

        # Test Case: Swap, hibernation
        mocked_config.storage.default_partitioning = [
            {
                'name': '/',
                'size': Size("50 GiB"),
            },
            {
                'name': 'swap',
            },
        ]
        partitioning_request = PartitioningRequest()
        partitioning_request.hibernation = True

        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert any(spec for spec in requests if spec.fstype == "swap")
        assert list(spec.size for spec in requests if spec.fstype == "swap") == [swap_size]
        suggest_swap_size.assert_called_with(hibernation=True, disk_space=ANY)

        # Test Case: Swap, no hibernation
        partitioning_request = PartitioningRequest()
        partitioning_request.hibernation = False

        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request
        )

        assert any(spec for spec in requests if spec.fstype == "swap")
        assert list(spec.size for spec in requests if spec.fstype == "swap") == [swap_size]
        suggest_swap_size.assert_called_with(hibernation=False, disk_space=ANY)

    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.conf')
    @patch('pyanaconda.modules.storage.partitioning.automatic.utils.platform')
    def test_get_partitioning_btrfs_only(self, platform, mocked_conf):
        storage = create_storage()
        platform.partitions = []

        # Set the default partitioning.
        mocked_conf.storage.default_partitioning = [
            {
                'name': '/',
                'size': Size("50 GiB"),
            }, {
                'name': '/var',
                'btrfs': True,
            }
        ]

        # Collect the requests for the Btrfs scheme.
        partitioning_request = PartitioningRequest()
        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_BTRFS,
            request=partitioning_request,
        )

        assert ["/", "/var"] == [spec.mountpoint for spec in requests]

        # Collect the requests for the LVM scheme.
        partitioning_request = PartitioningRequest()
        requests = AutomaticPartitioningTask._get_partitioning(
            storage=storage,
            scheme=AUTOPART_TYPE_LVM,
            request=partitioning_request,
        )

        assert ["/"] == [spec.mountpoint for spec in requests]


class AutomaticPartitioningTaskReuseTestCase(unittest.TestCase):
    """Test the automatic partitioning task mountpoint reuse functionality."""

    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.destroy_device')
    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.platform')
    def test_remove_bootloder_partitions(self, platform, destroy_device):
        storage = Mock()

        # Test platfrorm bootloader partitions

        # Test no bootoloaer partition required
        platform.partitions = [
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB"),
                lv=False,
            ),
        ]
        assert AutomaticPartitioningTask._remove_bootloader_partitions(storage) is False

        # Test multiple bootloader partitions required
        platform.partitions = [
            PartSpec(
                fstype="biosboot",
                size=Size("1MiB"),
            ),
            PartSpec(
                mountpoint="/boot/efi",
                fstype="efi",
                size=Size("500MiB"),
                max_size=Size("600MiB"),
                grow=True,
            )
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._remove_bootloader_partitions(storage)

        # biosboot
        platform.partitions = [
            # boot partition is ignored
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB"),
                lv=False
            ),
            PartSpec(
                fstype="biosboot",
                size=Size("1MiB")
            ),
        ]
        biosboot_device = Mock(format=Mock(type="biosboot"))
        storage.devices = [
            biosboot_device,
            Mock(format=Mock(type="xfs")),
        ]

        assert AutomaticPartitioningTask._remove_bootloader_partitions(storage) is True
        destroy_device.assert_called_with(storage, biosboot_device)

        # biosboot, two found
        biosboot_device1 = Mock(format=Mock(type="biosboot"))
        biosboot_device2 = Mock(format=Mock(type="biosboot"))
        biosboot_device1.name = "bd1"
        biosboot_device2.name = "bd2"
        storage.devices = [
            biosboot_device1,
            biosboot_device2,
            Mock(format=Mock(type="xfs")),
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._remove_bootloader_partitions(storage)

        # bootloader part not found
        storage.devices = [
            Mock(format=Mock(type="xfs")),
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._remove_bootloader_partitions(storage)
        assert AutomaticPartitioningTask._remove_bootloader_partitions(
            storage, required=False
        ) is False

        # prepboot
        platform.partitions = [
            PartSpec(
                fstype="prepboot",
                size=Size("4MiB")
            ),
        ]
        biosboot_device = Mock(format=Mock(type="prepboot"))
        storage.devices = [
            biosboot_device,
            Mock(format=Mock(type="xfs")),
        ]
        assert AutomaticPartitioningTask._remove_bootloader_partitions(storage) is True
        destroy_device.assert_called_with(storage, biosboot_device)

        # appleboot
        platform.partitions = [
            PartSpec(
                fstype="appleboot",
                size=Size("1MiB")
            ),
        ]
        biosboot_device = Mock(format=Mock(type="appleboot"))
        storage.devices = [
            biosboot_device,
            Mock(format=Mock(type="xfs")),
        ]
        assert AutomaticPartitioningTask._remove_bootloader_partitions(storage) is True
        destroy_device.assert_called_with(storage, biosboot_device)

        # prepboot
        platform.partitions = [
            PartSpec(
                mountpoint="/boot/efi",
                fstype="efi",
                size=Size("500MiB"),
                max_size=Size("600MiB"),
                grow=True,
            )
        ]
        biosboot_device = Mock(format=Mock(type="efi"))
        storage.devices = [
            biosboot_device,
            Mock(format=Mock(type="xfs")),
        ]
        assert AutomaticPartitioningTask._remove_bootloader_partitions(storage) is True
        destroy_device.assert_called_with(storage, biosboot_device)

    def test_get_mountpoint_device(self):
        storage = Mock()

        # device found
        home_device = Mock()
        storage.roots = [
            Mock(mounts={
                "/home": home_device,
                "/": Mock(),
            }),
        ]
        assert AutomaticPartitioningTask._get_mountpoint_device(
            storage, "/home"
        ) == home_device

        # device not found
        storage.roots = [
            Mock(mounts={
                "/": Mock(),
            }),
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._get_mountpoint_device(storage, "/home")
        assert AutomaticPartitioningTask._get_mountpoint_device(
            storage, "/home", required=False
        ) is None

        # multiple devices found
        home_device1 = Mock()
        home_device2 = Mock()
        home_device1.name = "device1_name"
        home_device2.name = "device2_name"
        storage.roots = [
            Mock(mounts={
                "/home": home_device1,
                "/": Mock(),
            }),
            Mock(mounts={
                "/home": home_device2,
            }),
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._get_mountpoint_device(storage, "/home")

    def test_get_mountpoint_options(self):
        storage = Mock()
        home_opts = "subvol=home,compress=zstd:1"
        storage.roots = [
            Mock(mountopts={
                "/home": home_opts
            }),
        ]
        assert AutomaticPartitioningTask._get_mountpoint_options(
            storage, "/home"
        ) == home_opts
        assert AutomaticPartitioningTask._get_mountpoint_options(
            storage, "/"
        ) is None

    def test_get_reused_device_names(self):
        request = Mock(
            reused_mount_points=["/home"],
            reformatted_mount_points=["/"]
        )
        storage = Mock()
        device1 = Mock()
        device1.name = "home"
        device2 = Mock()
        device2.name = "root"
        storage.roots = [
            Mock(mounts={
                "/home": device1,
                "/": device2,
            }),
        ]
        assert AutomaticPartitioningTask._get_reused_device_names(
            storage, request
        ) == {
            "home": "/home",
            "root": "/",
        }

    def test_check_reused_scheme(self):
        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_BTRFS,
            reused_mount_points=["/home"],
        )
        storage = Mock()
        storage.roots = [
            Mock(mounts={
                "/home": Mock(type="btrfs subvolume")
            }),
        ]
        AutomaticPartitioningTask._check_reused_scheme(storage, request)

        # all reused mountpoints must have the type based on the scheme
        request.reused_mount_points = ["/home", "/data"]
        storage.roots = [
            Mock(mounts={
                "/home": Mock(type="btrfs subvolume"),
                "/data": Mock(type="partition"),
            }),
        ]
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._check_reused_scheme(storage, request)

    def _get_mocked_storage_w_existing_system(self,
                                              bootloader_type="efi",
                                              root_device_type="btrfs subvolume",
                                              root_format_type="btrfs",
                                              separate_boot=True,
                                              ):
        storage = Mock()

        bootloader_device = Mock(format=Mock(type=bootloader_type), type="partition")
        bootloader_device.name = "vda1"
        root_device = Mock(format=Mock(type=root_format_type), type=root_device_type)
        root_device.name = "root"
        home_device = Mock(format=Mock(type=root_format_type), type=root_device_type)
        home_device.name = "home"

        storage.devices = [
            bootloader_device,
            root_device,
            home_device,
        ]
        if separate_boot:
            boot_device = Mock(format=Mock(type="ext4"), type="partition")
            boot_device.name = "vda2"
            storage.devices.append(boot_device)
        else:
            boot_device = None

        storage.roots = [
            Mock(mounts={
                "/home": home_device,
                "/": root_device,
            }),
        ]
        if separate_boot:
            storage.roots[0].mounts["/boot"] = boot_device

        return storage, bootloader_device, boot_device, root_device, home_device

    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.reformat_device')
    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.destroy_device')
    @patch('pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning.platform')
    def test_clear_existing_mountpoints(self, platform, destroy_device, reformat_device):
        # Existing btrfs with efi

        platform.partitions = [
            PartSpec(
                mountpoint="/boot/efi",
                fstype="efi",
                size=Size("500MiB"),
                max_size=Size("600MiB"),
                grow=True,
            ),
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB"),
                lv=False
            ),
        ]

        storage, bootloader_device, boot_device, root_device, _home_device = \
            self._get_mocked_storage_w_existing_system()

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_BTRFS,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/"],
        )

        expected_reused_devices = {
            "home": "/home",
            "root": "/",
        }
        AutomaticPartitioningTask._clear_existing_mountpoints(storage, request)
        destroy_device.assert_has_calls([
            call(storage, bootloader_device),
            call(storage, boot_device),
        ], any_order=True)
        reformat_device.assert_called_with(storage, root_device,
                                           dependencies=expected_reused_devices)

        # missing mountpoint to be removed (/boot) is ignored
        storage, bootloader_device, _boot_device, _root_device, _home_device = \
            self._get_mocked_storage_w_existing_system(separate_boot=False)
        destroy_device.reset_mock()
        AutomaticPartitioningTask._clear_existing_mountpoints(storage, request)
        destroy_device.assert_called_once_with(storage, bootloader_device)

        # missing mountpoint to be reformatted (/data) prevents the reuse
        storage, _bootloader_device, _boot_device, _root_device, _home_device = \
            self._get_mocked_storage_w_existing_system()

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_BTRFS,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/", "/data"],
        )
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._clear_existing_mountpoints(storage, request)

        # Existing plain with biosboot

        platform.partitions = [
            PartSpec(
                fstype="biosboot",
                size=Size("1MiB"),
            ),
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB"),
                lv=False
            ),
        ]
        storage, bootloader_device, boot_device, _root_device, _home_device = \
            self._get_mocked_storage_w_existing_system(
                root_device_type="partition",
                root_format_type="xfs",
                bootloader_type="biosboot"
            )

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_PLAIN,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader", "/"],
            reformatted_mount_points=[],
        )

        expected_reused_devices = {
            "home": "/home",
        }
        destroy_device.reset_mock()
        reformat_device.reset_mock()
        AutomaticPartitioningTask._clear_existing_mountpoints(storage, request)
        destroy_device.assert_has_calls([
            call(storage, bootloader_device),
            call(storage, boot_device),
        ], any_order=True)
        reformat_device.assert_not_called()

        # Existing lvm with efi without separate /boot

        platform.partitions = [
            PartSpec(
                mountpoint="/boot/efi",
                fstype="efi",
                size=Size("500MiB"),
                max_size=Size("600MiB"),
                grow=True,
            ),
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB"),
                lv=False
            ),
        ]

        storage, bootloader_device, _boot_device, root_device, _home_device = \
            self._get_mocked_storage_w_existing_system(
                root_device_type="lvmlv",
                root_format_type=None,
                separate_boot=False,
            )

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_LVM,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/"],
        )

        expected_reused_devices = {
            "home": "/home",
            "root": "/",
        }
        destroy_device.reset_mock()
        reformat_device.reset_mock()
        AutomaticPartitioningTask._clear_existing_mountpoints(storage, request)
        destroy_device.assert_called_once_with(storage, bootloader_device)
        reformat_device.assert_called_with(storage, root_device,
                                           dependencies=expected_reused_devices)

    def test_schedule_existing_mountpoints(self):
        # Existing btrfs with efi

        storage, _bootloader_device, _boot_device, _root_device, home_device = \
            self._get_mocked_storage_w_existing_system()

        home_opts = "subvol=home,compress=zstd:1"
        storage.roots[0].mountopts = {
            "/home": home_opts
        }

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_BTRFS,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/"],
        )

        reformatted_device = Mock()
        storage.devicetree.resolve_device.return_value = reformatted_device

        AutomaticPartitioningTask._schedule_existing_mountpoints(storage, request)
        assert home_device.format.mountpoint == "/home"
        assert home_device.format.options == home_opts
        assert reformatted_device.format.mountpoint == "/"

        # missing mountpoint to be reused (/home) prevents the reuse
        storage.roots[0].mounts.pop("/home")
        with pytest.raises(StorageError):
            AutomaticPartitioningTask._schedule_existing_mountpoints(storage, request)

        # Existing plain with biosboot

        storage, _bootloader_device, _boot_device, _root_device, home_device = \
            self._get_mocked_storage_w_existing_system(
                root_device_type="partition",
                root_format_type="xfs",
                bootloader_type="biosboot"
            )

        home_opts = "defaults"
        storage.roots[0].mountopts = {
            "/home": home_opts
        }

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_PLAIN,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader", "/"],
            reformatted_mount_points=[],
        )

        AutomaticPartitioningTask._schedule_existing_mountpoints(storage, request)
        assert home_device.format.mountpoint == "/home"
        assert home_device.format.options == home_opts

        # Existing lvm with efi without separate /boot

        storage, _bootloader_device, _boot_device, _root_device, home_device = \
            self._get_mocked_storage_w_existing_system(
                root_device_type="lvmlv",
                root_format_type=None,
                separate_boot=False,
            )

        home_opts = "defaults"
        storage.roots[0].mountopts = {
            "/home": home_opts
        }

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_LVM,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/"],
        )

        reformatted_device = Mock()
        storage.devicetree.resolve_device.return_value = reformatted_device

        AutomaticPartitioningTask._schedule_existing_mountpoints(storage, request)
        assert home_device.format.mountpoint == "/home"
        assert home_device.format.options == home_opts
        assert reformatted_device.format.mountpoint == "/"

    def test_implicit_partitions_reused(self):
        storage, _bootloader_device, _boot_device, root_device, home_device = \
            self._get_mocked_storage_w_existing_system()

        request = Mock(
            partitioning_scheme=AUTOPART_TYPE_BTRFS,
            reused_mount_points=["/home"],
            removed_mount_points=["/boot", "bootloader"],
            reformatted_mount_points=["/"],
        )

        # Make sure there is no 'vg' or 'volume' attribute
        home_device.mock_add_spec(['format', 'name'])
        root_device.mock_add_spec(['format', 'name'])
        assert AutomaticPartitioningTask._implicit_partitions_reused(storage, request) is False

        # / is on volume group
        root_device.mock_add_spec(['format', 'name', 'vg'])
        assert AutomaticPartitioningTask._implicit_partitions_reused(storage, request) is True

        # / is on btrfs
        root_device.mock_add_spec(['format', 'name', 'volume'])
        assert AutomaticPartitioningTask._implicit_partitions_reused(storage, request) is True


class AutomaticPartitioningUtilsTestCase(unittest.TestCase):
    """Test the automatic partitioning utils."""

    def test_get_disks_for_implicit_partitions(self):
        """Test the get_disks_for_implicit_partitions function."""
        # The /boot partition always requires a slot.
        requests = [
            PartSpec(
                mountpoint="/boot",
                size=Size("1GiB")
            ),
            PartSpec(
                mountpoint="/",
                size=Size("2GiB"),
                max_size=Size("15GiB"),
                grow=True,
                btr=True,
                lv=True,
                thin=True,
                encrypted=True
            ),
            PartSpec(
                fstype="swap",
                grow=False,
                lv=True,
                encrypted=True
            )
        ]

        # No implicit partitions to schedule.
        disk_1 = Mock()
        disk_2 = Mock()

        parted_disk_1 = disk_1.format.parted_disk
        parted_disk_2 = disk_2.format.parted_disk

        assert get_disks_for_implicit_partitions(
                scheme=AUTOPART_TYPE_PLAIN,
                disks=[disk_1, disk_2],
                requests=requests
            ) == \
            []

        # Extended partitions are supported by the first disk.
        parted_disk_1.supportsFeature.return_value = True
        parted_disk_1.maxPrimaryPartitionCount = 3
        parted_disk_1.primaryPartitionCount = 3

        parted_disk_2.supportsFeature.return_value = False
        parted_disk_2.maxPrimaryPartitionCount = 3
        parted_disk_2.primaryPartitionCount = 2

        assert get_disks_for_implicit_partitions(
                scheme=AUTOPART_TYPE_LVM_THINP,
                disks=[disk_1, disk_2],
                requests=requests
            ) == \
            [disk_1, disk_2]

        # Extended partitions are not supported by the first disk.
        parted_disk_1.supportsFeature.return_value = False
        parted_disk_1.maxPrimaryPartitionCount = 3
        parted_disk_1.primaryPartitionCount = 2

        assert get_disks_for_implicit_partitions(
                scheme=AUTOPART_TYPE_LVM_THINP,
                disks=[disk_1, disk_2],
                requests=requests
            ) == \
            [disk_2]

        # Not empty slots for implicit partitions.
        parted_disk_1.supportsFeature.return_value = False
        parted_disk_1.maxPrimaryPartitionCount = 3
        parted_disk_1.primaryPartitionCount = 3

        assert get_disks_for_implicit_partitions(
                scheme=AUTOPART_TYPE_LVM_THINP,
                disks=[disk_1, disk_2],
                requests=requests
            ) == \
            []
