#
# Copyright (C) 2021  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from dasbus.structure import compare_data
from dasbus.typing import get_variant, Bool, UInt16

from pyanaconda.modules.boss.user_interface import UIModule
from pyanaconda.modules.boss.user_interface.ui_interface import UIInterface
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class UIInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the user interface module."""

    def setUp(self):
        """Set up the module."""
        self.module = UIModule()
        self.interface = UIInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            USER_INTERFACE,
            self.interface,
            *args, **kwargs
        )

    def test_default_password_policies(self):
        """Test the password policies property."""
        policies = PasswordPolicy.from_structure_dict(
            self.interface.PasswordPolicies)

        expected_names = {"root", "user", "luks"}
        assert policies.keys() == expected_names

        for name in expected_names:
            policy = policies[name]
            expected_policy = PasswordPolicy.from_defaults(name)
            assert compare_data(policy, expected_policy)

    def test_password_policies_property(self):
        """Test the password policies property."""
        policy = {
            "min-quality": get_variant(UInt16, 10),
            "min-length": get_variant(UInt16, 20),
            "allow-empty": get_variant(Bool, True),
            "is-strict": get_variant(Bool, False)
        }

        self._check_dbus_property(
            "PasswordPolicies",
            {"luks": policy}
        )
