#
# Copyright (C) 2013  Red Hat, Inc.
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
from pyanaconda import keyboard
import unittest
import pytest

from unittest.mock import patch


class KeyboardUtilsTestCase(unittest.TestCase):
    """Test the keyboard utils."""

    @patch("pyanaconda.keyboard.conf")
    @patch("pyanaconda.keyboard.execWithRedirect")
    def test_can_configure_keyboard(self, exec_mock, conf_mock):
        """Check if the keyboard configuration is enabled or disabled."""
        # It's a dir installation.
        conf_mock.system.can_configure_keyboard = False
        conf_mock.system.can_run_on_xwayland = False
        assert keyboard.can_configure_keyboard() is False
        exec_mock.assert_not_called()

        # It's a boot.iso.
        conf_mock.system.can_configure_keyboard = True
        conf_mock.system.can_run_on_xwayland = False
        assert keyboard.can_configure_keyboard() is True
        exec_mock.assert_not_called()

        # It's a Live installation on Wayland.
        conf_mock.system.can_configure_keyboard = True
        conf_mock.system.can_run_on_xwayland = True
        exec_mock.return_value = 0
        assert keyboard.can_configure_keyboard() is False
        exec_mock.assert_called_once_with('xisxwayland', [])
        exec_mock.reset_mock()

        # It's a Live installation and not on Wayland.
        conf_mock.system.can_configure_keyboard = True
        conf_mock.system.can_run_on_xwayland = True
        exec_mock.return_value = 1  # xisxwayland returns 1 if it is not XWayland
        assert keyboard.can_configure_keyboard() is True
        exec_mock.assert_called_once_with('xisxwayland', [])
        exec_mock.reset_mock()

        # It's a Live installation and probably not on Wayland,
        # because the xisxwayland tooling is not present.
        conf_mock.system.can_configure_keyboard = True
        conf_mock.system.can_run_on_xwayland = True
        exec_mock.side_effect = FileNotFoundError()

        with self.assertLogs(level="WARNING") as cm:
            keyboard.can_configure_keyboard()

        msg = "The xisxwayland tool is not available!"
        assert any(map(lambda x: msg in x, cm.output))

        exec_mock.assert_called_once_with('xisxwayland', [])
        exec_mock.reset_mock()


class ParsingAndJoiningTests(unittest.TestCase):

    def test_layout_variant_parsing(self):
        """Should correctly parse keyboard layout and variant string specs."""

        # valid layout variant specs
        layout, variant = keyboard.parse_layout_variant("cz (qwerty)")
        assert layout == "cz"
        assert variant == "qwerty"

        layout, variant = keyboard.parse_layout_variant("cz (dvorak-ucw)")
        assert layout == "cz"
        assert variant == "dvorak-ucw"

        # a valid layout variant spec with no variant specified
        layout, variant = keyboard.parse_layout_variant("cz")
        assert layout == "cz"
        assert variant == ""

        # a valid layout variant spec containing a slash
        layout, variant = keyboard.parse_layout_variant("nec_vndr/jp")
        assert layout == "nec_vndr/jp"
        assert variant == ""

        # an invalid layout variant spec (missing layout)
        with pytest.raises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("")

        # another invalid layout variant spec (invalid layout)
        with pytest.raises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("&*&%$")

        # another invalid layout variant spec (square brackets)
        with pytest.raises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("cz [qwerty]")

        # another invalid layout variant spec (invalid variant)
        with pytest.raises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("cz (&*&*)")

    def test_layout_variant_joining(self):
        """Should correctly join keyboard layout and variant to a string spec."""

        # both layout and variant specified
        assert keyboard.join_layout_variant("cz", "qwerty") == "cz (qwerty)"

        # no variant specified
        assert keyboard.join_layout_variant("cz") == "cz"

    def test_layout_variant_parse_join(self):
        """Parsing and joining valid layout and variant spec should have no effect."""

        specs = ("cz", "cz (qwerty)")
        for spec in specs:
            (layout, variant) = keyboard.parse_layout_variant(spec)
            assert spec == keyboard.join_layout_variant(layout, variant)

    def test_layout_variant_normalize(self):
        """Normalizing layout and variant strings should work as expected."""

        # no effect on normalized layout and variant string
        assert keyboard.normalize_layout_variant("cz (qwerty)") == "cz (qwerty)"
        assert keyboard.normalize_layout_variant("cz") == "cz"

        # normalize spaces
        assert keyboard.normalize_layout_variant("cz(qwerty)") == "cz (qwerty)"
        assert keyboard.normalize_layout_variant("cz ( qwerty )") == "cz (qwerty)"
        assert keyboard.normalize_layout_variant("cz ") == "cz"
