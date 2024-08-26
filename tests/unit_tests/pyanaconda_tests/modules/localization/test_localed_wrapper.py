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
        assert localed_wrapper.current_layout_variant == "cz (qwerty)"
        assert localed_wrapper.options == \
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"]

        mocked_localed_proxy.VConsoleKeymap = ""
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        mocked_localed_proxy.X11Options = ""
        assert localed_wrapper.keymap == ""
        assert localed_wrapper.options == []
        assert localed_wrapper.layouts_variants == []
        assert localed_wrapper.current_layout_variant == ""

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

        # verify that user defined list doesn't change
        localed_wrapper._user_layouts_variants = []
        localed_wrapper.set_keymap("cz")
        localed_wrapper.convert_keymap("cz")
        localed_wrapper.set_and_convert_keymap("cz")
        assert localed_wrapper._user_layouts_variants == []
        # only set_layouts should change user defined layouts
        localed_wrapper.set_layouts(["cz", "us (euro)"])
        assert localed_wrapper._user_layouts_variants == ["cz", "us (euro)"]

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    def test_localed_wrapper_no_systembus(self, mocked_system_bus):
        """Test LocaledWrapper in environment without system bus.

        Which is also the environment of our tests.
        """
        # Emulates mock environment
        mocked_system_bus.check_connection.return_value = False
        localed_wrapper = LocaledWrapper()
        self._guarded_localed_wrapper_calls_check(localed_wrapper)

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_set_current_layout(self, mocked_conf,
                                                mocked_localed_service,
                                                mocked_system_bus):
        """Test LocaledWrapper method to set current layout to compositor.

        Verify that the layout to be set is moved to the first place.
        """
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        localed_wrapper = LocaledWrapper()
        user_defined = ["cz (qwerty)", "fi", "us (euro)", "fr"]

        # check if layout is correctly set
        localed_wrapper._user_layouts_variants = user_defined
        localed_wrapper.set_current_layout("fi")
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fi,us,fr,cz",
            "pc105",  # hardcoded
            ",euro,,qwerty",
            "",
            False,
            False
        )

        # check if layout is correctly set including variant
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.set_current_layout("us (euro)") is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us,fr,cz,fi",
            "pc105",  # hardcoded
            "euro,,qwerty,",
            "",
            False,
            False
        )

        # check when we are selecting non-existing layout
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "fi"
        mocked_localed_proxy.X11Variant = ""
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.set_current_layout("cz") is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

        # check when the layout set is empty
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.set_current_layout("fr") is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fr,cz,fi,us",
            "pc105",  # hardcoded
            ",qwerty,,euro",
            "",
            False,
            False
        )

        # can't set layout when we don't have user defined set
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz, us"
        mocked_localed_proxy.X11Variant = ""
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.set_current_layout("cz (qwerty)") is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

    @patch("pyanaconda.modules.localization.localed.SystemBus")
    @patch("pyanaconda.modules.localization.localed.LOCALED")
    @patch("pyanaconda.modules.localization.localed.conf")
    def test_localed_wrapper_set_next_layout(self, mocked_conf,
                                             mocked_localed_service,
                                             mocked_system_bus):
        """Test LocaledWrapper method to set current layout to compositor.

        Verify that we are selecting next layout to what is currently set in compositor.
        Because setting current layout changing the ordering we have to decide next layout based
        on the user selection.
        """
        mocked_system_bus.check_connection.return_value = True
        mocked_conf.system.provides_system_bus = True
        mocked_localed_proxy = Mock()
        mocked_localed_service.get_proxy.return_value = mocked_localed_proxy
        #  currently selected is first in this list 'cz (qwerty)'
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        localed_wrapper = LocaledWrapper()

        # test switch to next layout
        user_defined = ["cz (qwerty)", "fi", "us (euro)", "fr"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "fi,us,fr,cz",
            "pc105",  # hardcoded
            ",euro,,qwerty",
            "",
            False,
            False
        )

        # test switch to next layout in the middle of user defined list
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        user_defined = ["es", "cz (qwerty)", "us (euro)", "fr"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "us,fr,es,cz",
            "pc105",  # hardcoded
            "euro,,,qwerty",
            "",
            False,
            False
        )

        # test switch to next layout with different user defined list
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        user_defined = ["cz (qwerty)", "es"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "es,cz",
            "pc105",  # hardcoded
            ",qwerty",
            "",
            False,
            False
        )

        # the compositor list is empty test
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        user_defined = ["cz (qwerty)", "es"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "cz,es",
            "pc105",  # hardcoded
            "qwerty,",
            "",
            False,
            False
        )

        # the user defined list is empty test
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz,fi,us,fr"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()

        # the user defined list has only one value
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = "cz,fi,us,es"
        mocked_localed_proxy.X11Variant = "qwerty,,euro"
        user_defined = ["es (euro)"]
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is True
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_called_once_with(
            "es",
            "pc105",  # hardcoded
            "euro",
            "",
            False,
            False
        )

        # everything is empty
        mocked_localed_proxy.SetX11Keyboard.reset_mock()
        mocked_localed_proxy.X11Layout = ""
        mocked_localed_proxy.X11Variant = ""
        user_defined = []
        localed_wrapper._user_layouts_variants = user_defined

        assert localed_wrapper.select_next_layout() is False
        assert user_defined == localed_wrapper._user_layouts_variants  # must not change
        mocked_localed_proxy.SetX11Keyboard.assert_not_called()
