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
from unittest.mock import patch

from pyanaconda.modules.localization.live_keyboard import (
    GnomeShellKeyboard,
    get_live_keyboard_instance,
)


class LiveSystemKeyboardTestCase(unittest.TestCase):
    @patch("pyanaconda.modules.localization.live_keyboard.conf")
    def test_get_live_keyboard_instance(self, mocked_conf):
        """Test get_live_keyboard_instance function."""
        mocked_conf.system.provides_liveuser = True
        assert isinstance(get_live_keyboard_instance(), GnomeShellKeyboard)

        mocked_conf.reset_mock()
        mocked_conf.system.provides_liveuser = False
        assert get_live_keyboard_instance() is None

    def _check_gnome_shell_layouts_conversion(self, mocked_exec_with_capture, system_input, output):
        mocked_exec_with_capture.reset_mock()
        mocked_exec_with_capture.return_value = system_input

        gs = GnomeShellKeyboard()

        assert gs.read_keyboard_layouts() == output
        mocked_exec_with_capture.assert_called_once_with(
            "gsettings",
            ["get", "org.gnome.desktop.input-sources", "sources"]
            )

    @patch("pyanaconda.modules.localization.live_keyboard.execWithCaptureAsLiveUser")
    def test_gnome_shell_keyboard(self, mocked_exec_with_capture):
        """Test GnomeShellKeyboard live instance layouts."""
        # test one simple layout set
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz')]",
            output=["cz"]
        )

        # test one complex layout is set
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz+qwerty')]",
            output=["cz (qwerty)"]
        )

        # test multiple layouts are set
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz+qwerty'), ('xkb', 'us'), ('xkb', 'cz+dvorak-ucw')]",
            output=["cz (qwerty)", "us", "cz (dvorak-ucw)"]
        )

        # test layouts with ibus (ibus is ignored)
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz'), ('ibus', 'libpinyin')]",
            output=["cz"]
        )

        # test only ibus layout
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('ibus', 'libpinyin')]",
            output=[]
        )

        # test wrong input
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"wrong input",
            output=[]
        )
