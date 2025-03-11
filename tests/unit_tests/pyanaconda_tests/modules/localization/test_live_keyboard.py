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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import patch

import pytest

from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError
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

    def _check_gnome_shell_layouts_conversion(self,
                                              mocked_exec_with_capture,
                                              system_input,
                                              output,
                                              unsupported_layout):
        mocked_exec_with_capture.reset_mock()
        mocked_exec_with_capture.return_value = system_input

        gs = GnomeShellKeyboard()

        if unsupported_layout:
            match = fr'.*{unsupported_layout}.*'
            with pytest.raises(KeyboardConfigurationError, match=match):
                gs.read_keyboard_layouts()
            return

        result = gs.read_keyboard_layouts()

        assert result == output
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
            output=["cz"],
            unsupported_layout=None
        )

        # test one complex layout is set
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz+qwerty')]",
            output=["cz (qwerty)"],
            unsupported_layout=None
        )

        # test multiple layouts are set
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz+qwerty'), ('xkb', 'us'), ('xkb', 'cz+dvorak-ucw')]",
            output=["cz (qwerty)", "us", "cz (dvorak-ucw)"],
            unsupported_layout=None
        )

        # test layouts with ibus (ibus will raise error)
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('xkb', 'cz'), ('ibus', 'libpinyin')]",
            output=[],
            unsupported_layout='libpinyin'
        )

        # test only ibus layout (raise the error)
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"[('ibus', 'libpinyin')]",
            output=[],
            unsupported_layout='libpinyin'
        )

        # test wrong input
        self._check_gnome_shell_layouts_conversion(
            mocked_exec_with_capture=mocked_exec_with_capture,
            system_input=r"wrong input",
            output=[],
            unsupported_layout=None
        )
