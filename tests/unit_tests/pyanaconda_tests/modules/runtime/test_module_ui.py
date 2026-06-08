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
from dasbus.typing import Bool, Str, UInt16, get_variant
from pykickstart.commands.displaymode import (
    DISPLAY_MODE_CMDLINE,
    DISPLAY_MODE_GRAPHICAL,
    DISPLAY_MODE_TEXT,
)

from pyanaconda.core.constants import DisplayModes
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from pyanaconda.modules.common.structures.product import ProductData
from pyanaconda.modules.common.structures.rdp import RdpData
from pyanaconda.modules.runtime.runtime import RuntimeService
from pyanaconda.modules.runtime.runtime_interface import RuntimeInterface
from pyanaconda.modules.runtime.user_interface import UIModule
from pyanaconda.modules.runtime.user_interface.ui_interface import UIInterface
from tests.unit_tests.pyanaconda_tests import check_dbus_property, check_kickstart_interface


class UIInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the user interface module."""

    def setUp(self):
        """Set up the module."""
        self.module = UIModule()
        self.interface = UIInterface(self.module)
        self.runtime_service = RuntimeService()
        self.runtime_interface = RuntimeInterface(self.runtime_service)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            USER_INTERFACE,
            self.interface,
            *args, **kwargs
        )

    def _test_runtime_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.runtime_interface, ks_in, ks_out)

    def test_default_password_policies(self):
        """Test the password policies property."""
        policies = PasswordPolicy.from_structure_dict(
            self.interface.PasswordPolicies
        )

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

    def test_product_data_property(self):
        """Test the ProductData property."""
        # Fetch the ProductData from the DBus interface
        product_data = ProductData.from_structure(self.interface.ProductData)

        # Check if the product data has the correct structure
        assert isinstance(product_data, ProductData)
        assert isinstance(product_data.is_final_release, Bool)
        assert isinstance(product_data.name, Str)
        assert isinstance(product_data.version, Str)
        assert isinstance(product_data.short_name, Str)

        assert product_data.is_final_release is False
        assert product_data.name == "anaconda"
        assert product_data.version == "bluesky"
        assert product_data.short_name == "anaconda"

    def test_display_mode_property(self):
        """Test the DisplayMode DBus property."""
        self._check_dbus_property(
            "DisplayMode",
            "GUI",
            out_value="GUI"
        )

    def test_display_mode_property_tui(self):
        """Test the DisplayMode DBus property for TUI."""
        self._check_dbus_property(
            "DisplayMode",
            "TUI",
            out_value="TUI"
        )

    def test_display_mode_property_normalizes_kickstart_values(self):
        """Test DisplayMode returns normalized DBus values for kickstart strings."""
        self.module.set_display_mode(DISPLAY_MODE_GRAPHICAL)
        assert self.interface.DisplayMode == "GUI"

        self.module.set_display_mode(DISPLAY_MODE_TEXT)
        assert self.interface.DisplayMode == "TUI"

        self.module.set_display_mode(DISPLAY_MODE_CMDLINE)
        assert self.interface.DisplayMode == "cmdline"

    def test_display_mode_property_accepts_cmdline(self):
        """Test DisplayMode DBus property accepts cmdline."""
        self._check_dbus_property(
            "DisplayMode",
            "cmdline",
            out_value="cmdline"
        )

    def test_display_mode_non_interactive_property(self):
        """Test the DisplayModeNonInteractive DBus property."""
        self._check_dbus_property(
            "DisplayModeNonInteractive",
            True
        )

    def test_display_mode_text_kickstarted_property(self):
        """Test the DisplayModeTextKickstarted DBus property."""
        assert self.interface.DisplayModeTextKickstarted is False

    def test_rdp_property(self):
        """Test the Rdp DBus property."""
        rdp = RdpData()
        rdp.enabled = True
        rdp.username = "anacondauser"
        rdp.password.set_secret("testpassword")

        self._check_dbus_property(
            "Rdp",
            RdpData.to_structure(rdp)
        )

    def test_set_display_mode_none(self):
        """Test that None input doesn't override display mode."""
        self.module.set_display_mode(DisplayModes.GUI)
        self.module.set_display_mode(None)
        assert self.module.display_mode == DisplayModes.GUI

    def test_kickstart_graphical(self):
        """Test graphical mode via runtime kickstart processing."""
        ks_in = "graphical\n"
        ks_out = "# Use graphical install\ngraphical\n"
        self._test_runtime_kickstart(ks_in, ks_out)
        assert self.runtime_service._ui_module.display_mode == DISPLAY_MODE_GRAPHICAL

    def test_kickstart_text(self):
        """Test text mode and explicit text flag via runtime kickstart processing."""
        ks_in = "text\n"
        ks_out = "# Use text mode install\ntext\n"
        self._test_runtime_kickstart(ks_in, ks_out)
        assert self.runtime_service._ui_module.display_mode == DISPLAY_MODE_TEXT
        assert self.runtime_service._ui_module.display_mode_text_kickstarted is True

    def test_kickstart_cmdline(self):
        """Test cmdline mode via runtime kickstart processing."""
        ks_in = "cmdline\n"
        ks_out = "cmdline\n"
        self._test_runtime_kickstart(ks_in, ks_out)
        assert self.runtime_service._ui_module.display_mode == DISPLAY_MODE_CMDLINE

    def test_kickstart_rdp(self):
        """Test RDP command updates UI submodule via runtime kickstart processing."""
        ks_in = "rdp --username=anacondauser --password=testpassword\n"
        ks_out = "rdp --username=anacondauser --password=testpassword\n"
        self._test_runtime_kickstart(ks_in, ks_out)

        rdp = self.runtime_service._ui_module.rdp
        assert rdp.enabled is True
        assert rdp.username == "anacondauser"
        assert rdp.password.value == "testpassword"

    def test_read_empty_kickstart_keeps_default_display_mode(self):
        """Empty kickstart must not overwrite the default display mode with None."""
        self.runtime_interface.ReadKickstart("")

        ui_module = self.runtime_service._ui_module
        assert ui_module.display_mode == DisplayModes.TUI
        assert ui_module.display_mode_non_interactive is False
        assert ui_module.display_mode_text_kickstarted is False
