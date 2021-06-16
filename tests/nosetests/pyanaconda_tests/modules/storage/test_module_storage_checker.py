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

from blivet.size import Size
from dasbus.typing import get_variant, Int
from pyanaconda.core.constants import STORAGE_MIN_RAM, STORAGE_LUKS2_MIN_RAM
from pyanaconda.modules.common.errors.general import UnsupportedValueError
from pyanaconda.modules.storage.checker import StorageCheckerModule
from pyanaconda.modules.storage.checker.checker_interface import StorageCheckerInterface
from pyanaconda.modules.storage.checker.utils import storage_checker, verify_lvm_destruction


class StorageCheckerInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage checker module."""

    def setUp(self):
        self.module = StorageCheckerModule()
        self.interface = StorageCheckerInterface(self.module)

    @patch.dict(storage_checker.constraints)
    def set_constraint_test(self):
        """Test SetConstraint."""
        self.interface.SetConstraint(
            STORAGE_MIN_RAM,
            get_variant(Int, 987 * 1024 * 1024)
        )

        self.assertEqual(storage_checker.constraints[STORAGE_MIN_RAM], Size("987 MiB"))

        with self.assertRaises(UnsupportedValueError) as cm:
            self.interface.SetConstraint(
                STORAGE_LUKS2_MIN_RAM,
                get_variant(Int, 987 * 1024 * 1024)
            )

        self.assertEqual(str(cm.exception), "Constraint 'luks2_min_ram' is not supported.")
        self.assertEqual(storage_checker.constraints[STORAGE_LUKS2_MIN_RAM], Size("128 MiB"))


class StorageCheckerVerificationTestCase(unittest.TestCase):

    def lvm_verification_test(self):
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
