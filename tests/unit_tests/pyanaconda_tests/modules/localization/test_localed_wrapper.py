#
# Copyright (C) 2023  Red Hat, Inc.
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
import unittest
from unittest.mock import patch, Mock

from pyanaconda.modules.localization.localed import LocaledWrapper


class LocaledWrapperTestCase(unittest.TestCase):
    """Test LocaledWrapper."""

    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_no_systembus_conf(self, mocked_conf):
        """Test LocaledWrapper on environments with nonavailability of systembus configured."""
        mocked_conf.system.provides_system_bus = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)

    def _guarded_localed_wrapper_calls_check(self, localed_wrapper):
        """Test that calls to LocaledWrapper are guarded not to fail."""
        assert localed_wrapper.keymap == ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.set_layouts(["us-altgr-intl"])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_properties(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test conversion of return values from Localed service to LocaledWraper."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        localed_wrapper = LocaledWrapper()
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        assert localed_wrapper.keymap == \
            "cz"
        assert localed_wrapper.layouts_variants == \
            ["cz (qwerty)", "fi", "us (euro)", "fr"]
        assert localed_wrapper.options == \
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"]

        mocked_localed_proxy.VConsoleKeymap = ""
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        assert localed_wrapper.keymap == ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_safe_calls(self, mocked_conf, mocked_localed_service,
                                        mocked_system_bus):
        """Test calling LocaledWrapper with invalid values does not raise exception."""
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.VConsoleKeymap = "cz"
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        mocked_localed_proxy.X11Options = "grp:alt_shift_toggle,grp:ctrl_alt_toggle"
        localed_wrapper = LocaledWrapper()
        # valid values
        localed_wrapper.set_keymap("cz")
        localed_wrapper.set_keymap("cz", convert=True)
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        # invalid values
        localed_wrapper.set_keymap("iinvalid")
        localed_wrapper.set_keymap("iinvalid", convert=True)
        localed_wrapper.convert_keymap("iinvalid")
        localed_wrapper.set_and_convert_keymap("iinvalid")
        # valid values
        localed_wrapper.set_layouts(["cz (qwerty)", "us (euro)"],
                                    options="grp:alt_shift_toggle",
                                    convert=True)
        localed_wrapper.set_and_convert_layouts(["cz (qwerty)", "us (euro)"])
        localed_wrapper.convert_layouts(["cz (qwerty)", "us (euro)"])
        # invalid values
        # rhbz#1843379
        localed_wrapper.set_layouts(["us-altgr-intl"])
        localed_wrapper.set_and_convert_layouts(["us-altgr-intl"])
        localed_wrapper.convert_layouts(["us-altgr-intl"])

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    def test_localed_wrapper_no_systembus(self, mocked_system_bus):
        """Test LocaledWrapper in environment without system bus.

        Which is also the environment of our tests.
        """
        # Emulates mock environment
        mocked_system_bus.check_connection.return_value = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)
