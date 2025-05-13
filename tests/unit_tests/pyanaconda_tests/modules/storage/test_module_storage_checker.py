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
from functools import partial
from unittest.mock import Mock, PropertyMock, mock_open, patch

import pytest
from blivet.devices import StorageDevice
from blivet.formats import get_format
from blivet.formats.fs import XFS
from blivet.size import Size
from dasbus.typing import Int, get_variant

from pyanaconda.core.constants import STORAGE_LUKS2_MIN_RAM, STORAGE_MIN_RAM
from pyanaconda.modules.common.errors.general import UnsupportedValueError
from pyanaconda.modules.storage.checker import StorageCheckerModule
from pyanaconda.modules.storage.checker.checker_interface import StorageCheckerInterface
from pyanaconda.modules.storage.checker.utils import (
    _check_opal_firmware_kernel_version,
    _get_opal_firmware_kernel_version,
    storage_checker,
    verify_lvm_destruction,
    verify_opal_compatibility,
)
from pyanaconda.modules.storage.devicetree import create_storage


class StorageCheckerInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage checker module."""

    def setUp(self):
        self.module = StorageCheckerModule()
        self.interface = StorageCheckerInterface(self.module)

    @patch.dict(storage_checker.constraints)
    def test_set_constraint(self):
        """Test SetConstraint."""
        self.interface.SetConstraint(
            STORAGE_MIN_RAM,
            get_variant(Int, 987 * 1024 * 1024)
        )

        assert storage_checker.constraints[STORAGE_MIN_RAM] == Size("987 MiB")

        with pytest.raises(UnsupportedValueError) as cm:
            self.interface.SetConstraint(
                STORAGE_LUKS2_MIN_RAM,
                get_variant(Int, 987 * 1024 * 1024)
            )

        assert str(cm.value) == "Constraint 'luks2_min_ram' is not supported."
        assert storage_checker.constraints[STORAGE_LUKS2_MIN_RAM] == Size("128 MiB")


class StorageCheckerVerificationTestCase(unittest.TestCase):

    def test_lvm_verification(self):
        """Test the LVM destruction test."""
        # VG that is destroyed correctly
        action1 = Mock()
        action1.is_destroy = True
        action1.is_device = True
        action1.device.type = "lvmvg"
        action1.device.name = "VOLGROUP-A"

        # something to ignore
        action2 = Mock()
        action2.is_destroy = False

        # PV that belongs to VG from #1
        action3 = Mock()
        action3.is_destroy = True
        action3.is_format = True
        action3.orig_format.type = "lvmpv"
        action3.device.disk.name = "PHYSDISK-1"
        action3.orig_format.vg_name = "VOLGROUP-A"

        # PV that belongs to a missing group
        action4 = Mock()
        action4.is_destroy = True
        action4.is_format = True
        action4.orig_format.type = "lvmpv"
        action4.device.disk.name = "PHYSDISK-2"
        action4.orig_format.vg_name = "VOLGROUP-B"

        # PV that does not belong to any group
        action5 = Mock()
        action5.is_destroy = True
        action5.is_format = True
        action5.orig_format.type = "lvmpv"
        action5.device.disk.name = "PHYSDISK-3"
        action5.orig_format.vg_name = ""

        storage = Mock()
        storage.devicetree.actions = [action1, action2, action3, action4, action5]
        error_handler = Mock()
        warning_handler = Mock()

        verify_lvm_destruction(storage, None, error_handler, warning_handler)

        warning_handler.assert_not_called()
        error_handler.assert_called_once_with(
            "Selected disks {} contain volume group '{}' that also uses further unselected disks. "
            "You must select or de-select all these disks as a set."
            .format("PHYSDISK-2", "VOLGROUP-B")
        )

    def test_get_opal_kernel_version(self):
        """Test the function for getting the firmware kernel version."""
        patch_open = partial(patch, 'pyanaconda.modules.storage.checker.utils.open')

        with patch_open() as m:
            m.side_effect = OSError("Error!")
            assert _get_opal_firmware_kernel_version() is None

        with patch_open(mock_open(read_data=" 5.10.50\n")):
            assert _get_opal_firmware_kernel_version() == "5.10.50"

        with patch_open(mock_open(read_data="5.10.50-openpower1-p59fd803")):
            assert _get_opal_firmware_kernel_version() == "5.10.50-openpower1-p59fd803"

        with patch_open(mock_open(read_data="v4.15.9-openpower1-p9e03417")):
            assert _get_opal_firmware_kernel_version() == "4.15.9-openpower1-p9e03417"

    def test_check_opal_firmware_kernel_version(self):
        """Test the function for checking the firmware kernel version."""
        check = partial(_check_opal_firmware_kernel_version)

        assert not check(None, None)
        assert not check("", "")
        assert not check("5.09", "5.10")
        assert not check("5.9.1", "5.10")
        assert not check("5.9.50-openpower1-p59fd803", "5.10")
        assert not check("5.8", "5.10")
        assert not check("4.0-openpower1-p59fd803", "5.10")

        assert check("5.10", "5.10")
        assert check("5.10.1", "5.10")
        assert check("5.10.50-openpower1-p59fd803", "5.10")
        assert check("5.11", "5.10")
        assert check("6.0-openpower1-p59fd803", "5.10")

    @patch("pyanaconda.modules.storage.checker.utils.arch")
    def test_opal_verification_arch(self, mocked_arch):
        """Check verify_opal_compatibility with a different arch."""
        mocked_arch.get_arch.return_value = "x86_64"
        self._verify_opal_compatibility(message=None)

    @patch("pyanaconda.modules.storage.checker.utils.arch")
    def test_opal_verification_platform(self, mocked_arch):
        """Check verify_opal_compatibility with a different platform."""
        mocked_arch.get_arch.return_value = "ppc64le"
        mocked_arch.is_powernv.return_value = False
        self._verify_opal_compatibility(message=None)

    @patch("pyanaconda.modules.storage.checker.utils._get_opal_firmware_kernel_version")
    @patch("pyanaconda.modules.storage.checker.utils.arch")
    def test_opal_verification_new_firmware(self, mocked_arch, version_getter):
        """Check verify_opal_compatibility with a newer firmware."""
        mocked_arch.get_arch.return_value = "ppc64le"
        mocked_arch.is_powernv.return_value = True
        version_getter.return_value = "5.10.50-openpower1-p59fd803"
        self._verify_opal_compatibility(message=None)

    @patch.object(XFS, "mountable", new_callable=PropertyMock)
    @patch("pyanaconda.modules.storage.checker.utils._get_opal_firmware_kernel_version")
    @patch("pyanaconda.modules.storage.checker.utils.arch")
    def test_opal_verification_old_firmware(self, mocked_arch, version_getter, xfs_mountable):
        """Check verify_opal_compatibility with an older firmware."""
        message = \
            "The system will not be bootable. The firmware does not support " \
            "XFS file system features on the boot file system. Upgrade the " \
            "firmware or change the file system type."

        storage = create_storage()

        mocked_arch.get_arch.return_value = "ppc64le"
        mocked_arch.is_powernv.return_value = True
        version_getter.return_value = "5.9.50-openpower1-p59fd803"
        xfs_mountable.return_value = True

        # No devices.
        self._verify_opal_compatibility(storage, message=None)

        # No mount points.
        dev1 = StorageDevice("dev1", size=Size("10 GiB"))
        storage.devicetree._add_device(dev1)

        self._verify_opal_compatibility(storage, message=None)

        # Different filesystem.
        dev1.format = get_format("ext2", mountpoint="/boot")
        self._verify_opal_compatibility(storage, message=None)

        # XFS on /
        dev1.format = get_format("xfs", mountpoint="/")
        self._verify_opal_compatibility(storage, message=message)

        # XFS on /boot
        dev1.format = get_format("xfs", mountpoint="/boot")
        self._verify_opal_compatibility(storage, message=message)

    def _verify_opal_compatibility(self, storage=None, message=None):
        """Verify the OPAL compatibility."""
        reporter = Mock()
        verify_opal_compatibility(
            storage=storage,
            constraints={},
            report_error=reporter,
            report_warning=None
        )

        if not message:
            reporter.assert_not_called()
        else:
            reporter.assert_called_once_with(message)
