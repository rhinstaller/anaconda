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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import patch

import pytest

from pyanaconda import keyboard


class KeyboardUtilsTestCase(unittest.TestCase):
    """Test the keyboard utils."""

    @patch("pyanaconda.keyboard.conf")
    def test_can_configure_keyboard(self, conf_mock):
        """Check if the keyboard configuration is enabled or disabled."""
        # It's a dir installation.
        conf_mock.system.can_configure_keyboard = False
        assert keyboard.can_configure_keyboard() is False

        # It's a boot.iso.
        conf_mock.system.can_configure_keyboard = True
        assert keyboard.can_configure_keyboard() is True


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
