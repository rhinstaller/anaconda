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
from unittest.mock import mock_open, patch

from dasbus.structure import compare_data
from dasbus.typing import Bool, Str, UInt16, get_variant

from pyanaconda.core.product import ProductData as CoreProductData
from pyanaconda.core.product import get_product_values
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from pyanaconda.modules.common.structures.product import ProductData
from pyanaconda.modules.runtime.user_interface import UIModule
from pyanaconda.modules.runtime.user_interface.ui_interface import UIInterface
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

    @patch("pyanaconda.modules.runtime.user_interface.ui.get_product_values")
    def test_product_data_property(self, product_values):
        """Test the ProductData property."""
        for is_final in (False, True):
            with self.subTest(is_final=is_final):
                product_values.return_value = CoreProductData(
                    is_final, "Test Product", "43", "tp"
                )
                product_data = ProductData.from_structure(self.interface.ProductData)

                assert isinstance(product_data, ProductData)
                assert isinstance(product_data.is_final_release, Bool)
                assert isinstance(product_data.name, Str)
                assert isinstance(product_data.version, Str)
                assert isinstance(product_data.short_name, Str)

                assert product_data.is_final_release is is_final
                assert product_data.name == "Test Product"
                assert product_data.version == "43"
                assert product_data.short_name == "tp"

    @patch.dict("os.environ", clear=True)
    def test_product_data_release_type(self):
        """Expose os-release status to Web UI even when buildstamp disagrees."""
        self.addCleanup(get_product_values.cache_clear)

        for release_type, legacy_is_final, expected in (
            ("development", True, False),
            ("experiment", True, False),
            ("stable", False, True),
            ("lts", False, True),
            ("unknown", False, True),
            ("", True, False),
            ("", False, False),
            (None, True, False),
            (None, False, False),
        ):
            with self.subTest(release_type=release_type, legacy_is_final=legacy_is_final):
                get_product_values.cache_clear()
                os_release = mock_open(read_data=(
                    f'RELEASE_TYPE="{release_type}"\n' if release_type is not None else "ID=fedora\n"
                ))
                buildstamp = mock_open(read_data=f"[Main]\nIsFinal={legacy_is_final}\n")

                with patch("pyanaconda.core.os_release.open", os_release):
                    with patch("pyanaconda.core.product.configparser.open", buildstamp):
                        product_data = ProductData.from_structure(self.interface.ProductData)

                assert product_data.is_final_release is expected
