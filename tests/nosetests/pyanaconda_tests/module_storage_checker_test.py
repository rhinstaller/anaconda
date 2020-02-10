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
from unittest.mock import patch

from dasbus.typing import get_variant, Int
from pyanaconda.core.constants import STORAGE_MIN_RAM
from pyanaconda.modules.storage.checker import StorageCheckerModule
from pyanaconda.modules.storage.checker.checker_interface import StorageCheckerInterface
from pyanaconda.storage.checker import storage_checker


class StorageCheckerInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage checker module."""

    def setUp(self):
        self.module = StorageCheckerModule()
        self.interface = StorageCheckerInterface(self.module)

    def set_constraint_test(self):
        """Test SetConstraint."""
        with patch.dict(storage_checker.constraints):
            self.interface.SetConstraint(STORAGE_MIN_RAM, get_variant(Int, 987))
            self.assertEqual(storage_checker.constraints[STORAGE_MIN_RAM], 987)
