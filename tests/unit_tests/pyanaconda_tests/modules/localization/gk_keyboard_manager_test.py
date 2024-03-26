#
# Copyright (C) 2024  Red Hat, Inc.
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
import pytest

from unittest.mock import patch, Mock

from pyanaconda.modules.localization.gk_keyboard_manager import GkKeyboardManager
from pyanaconda.keyboard import KeyboardConfigError


LAYOUT_PROXY_MOCKS = {
    "/org/gnome/Kiosk/InputSources/xkb_fr":
    Mock(BackendType="xkb", BackendId="fr"),
    "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik":
    Mock(BackendType="xkb", BackendId="cn+mon_todo_galik"),
    "/org/gnome/Kiosk/InputSources/non-xkb_fr":
    Mock(BackendType="non-xkb", BackendId="fr"),
    "/org/gnome/Kiosk/InputSources/Manager":
    Mock(),
}

MockedGKIS = Mock()
MockedGKIS.get_proxy = lambda object_path: LAYOUT_PROXY_MOCKS[object_path]
MockedGKIS.object_path = "/org/gnome/Kiosk"


@patch("pyanaconda.modules.localization.gk_keyboard_manager.GK_INPUT_SOURCES", new=MockedGKIS)
class GkKeyboardManagerTestCase(unittest.TestCase):
    """Test the Gnome Kiosk keyboard manager."""

    def test_properties_changed(self):
        """Test _on_properties_changed callback"""
        mocked_manager = GkKeyboardManager()
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik",
            "/org/gnome/Kiosk/InputSources/xkb_fr"
        ]
        callback1_mock = Mock()
        callback2_mock = Mock()
        mocked_manager.compositor_selected_layout_changed.connect(callback1_mock)
        mocked_manager.compositor_layouts_changed.connect(callback2_mock)

        object_path_mock = Mock()
        object_path_mock.get_string.return_value = "/org/gnome/Kiosk/InputSources/xkb_fr"
        mocked_manager._on_properties_changed(
            "org.gnome.Kiosk.InputSources",
            {"SelectedInputSource": object_path_mock},
            {},
        )
        callback1_mock.assert_called_once_with("fr")
        callback2_mock.assert_not_called()

        mocked_manager._on_properties_changed(
            "org.gnome.Kiosk.InputSources",
            {"InputSources": ["/org/gnome/Kiosk/InputSources/xkb_fr"]},
            [],
        )
        callback1_mock.assert_called_once_with("fr")
        callback2_mock.assert_called_once_with(["fr"])

    def test_get_compositor_selected_layout(self):
        """Test the get_compositor_selected_layout method"""
        mocked_manager = GkKeyboardManager()
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik",
            "/org/gnome/Kiosk/InputSources/xkb_fr"
        ]

        mocked_manager._proxy.SelectedInputSource = "/"
        assert mocked_manager.get_compositor_selected_layout() == ""

        mocked_manager._proxy.SelectedInputSource = None
        assert mocked_manager.get_compositor_selected_layout() == ""

        layout_path = "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik"
        mocked_manager._proxy.SelectedInputSource = layout_path
        assert mocked_manager.get_compositor_selected_layout() == "cn (mon_todo_galik)"

    def test_set_compositor_selected_layout(self):
        """Test the set_compositor_selected_layout method"""

        mocked_manager = GkKeyboardManager()
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik",
            "/org/gnome/Kiosk/InputSources/xkb_fr"
        ]
        assert mocked_manager.set_compositor_selected_layout("cn (mon_todo_galik)") is True
        mocked_manager._proxy.SelectInputSource.assert_called_with(
            "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik"
        )

        # non-xkb type raises exception
        # (even in case there is xkb-type data for the layout)
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/non-xkb_fr",
            "/org/gnome/Kiosk/InputSources/xkb_fr"
        ]
        with pytest.raises(KeyboardConfigError):
            mocked_manager.set_compositor_selected_layout("fr")

        # Source not found
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/xkb_fr"
        ]
        assert mocked_manager.set_compositor_selected_layout("cn (mon_todo_galik)") is False

    def test_select_next_compositor_layout(self):
        """Test the select_next_compositor_layout method"""
        mocked_manager = GkKeyboardManager()
        mocked_manager.select_next_compositor_layout()
        mocked_manager._proxy.SelectNextInputSource.assert_called_once()

    def test_get_compositor_layouts(self):
        """Test the get_compositor_layouts method"""

        mocked_manager = GkKeyboardManager()
        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/xkb_cn_2b_mon_5f_todo_5f_galik",
            "/org/gnome/Kiosk/InputSources/xkb_fr",
        ]
        assert mocked_manager.get_compositor_layouts() == ["cn (mon_todo_galik)", "fr"]

        mocked_manager._proxy.InputSources = [
            "/org/gnome/Kiosk/InputSources/non-xkb_fr",
            "/org/gnome/Kiosk/InputSources/xkb_fr",
        ]
        with pytest.raises(KeyboardConfigError):
            mocked_manager.get_compositor_layouts()

    def test_set_compositor_layouts(self):
        """Test the set_compositor_layouts method"""
        mocked_manager = GkKeyboardManager()
        mocked_manager.set_compositor_layouts(
            ["cz (qwerty)", "fi", "us (euro)", "fr"],
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"],
        )
        mocked_manager._proxy.SetInputSources.assert_called_with(
            [("xkb", "cz+qwerty"), ("xkb", "fi"), ("xkb", "us+euro"), ("xkb", "fr")],
            ["grp:alt_shift_toggle", "grp:ctrl_alt_toggle"],
        )
