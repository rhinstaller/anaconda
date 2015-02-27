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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

from pyanaconda import keyboard
import unittest

class ParsingAndJoiningTests(unittest.TestCase):
    def layout_variant_parsing_test(self):
        """Should correctly parse keyboard layout and variant string specs."""

        # valid layout variant specs
        layout, variant = keyboard.parse_layout_variant("cz (qwerty)")
        self.assertEqual(layout, "cz")
        self.assertEqual(variant, "qwerty")

        layout, variant = keyboard.parse_layout_variant("cz (dvorak-ucw)")
        self.assertEqual(layout, "cz")
        self.assertEqual(variant, "dvorak-ucw")

        # a valid layout variant spec with no variant specified
        layout, variant = keyboard.parse_layout_variant("cz")
        self.assertEqual(layout, "cz")
        self.assertEqual(variant, "")

        # an invalid layout variant spec (missing layout)
        with self.assertRaises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("")

        # another invalid layout variant spec (invalid layout)
        with self.assertRaises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("&*&%$")

        # another invalid layout variant spec (square brackets)
        with self.assertRaises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("cz [qwerty]")

        # another invalid layout variant spec (invalid variant)
        with self.assertRaises(keyboard.InvalidLayoutVariantSpec):
            layout, variant = keyboard.parse_layout_variant("cz (&*&*)")

    def layout_variant_joining_test(self):
        """Should correctly join keyboard layout and variant to a string spec."""

        # both layout and variant specified
        self.assertEqual(keyboard._join_layout_variant("cz", "qwerty"),
                         "cz (qwerty)")

        # no variant specified
        self.assertEqual(keyboard._join_layout_variant("cz"), "cz")

    def layout_variant_parse_join_test(self):
        """Parsing and joining valid layout and variant spec should have no effect."""

        specs = ("cz", "cz (qwerty)")
        for spec in specs:
            (layout, variant) = keyboard.parse_layout_variant(spec)
            self.assertEqual(spec, keyboard._join_layout_variant(layout, variant))

    def layout_variant_normalize_test(self):
        """Normalizing layout and variant strings should work as expected."""

        # no effect on normalized layout and variant string
        self.assertEqual(keyboard.normalize_layout_variant("cz (qwerty)"), "cz (qwerty)")
        self.assertEqual(keyboard.normalize_layout_variant("cz"), "cz")

        # normalize spaces
        self.assertEqual(keyboard.normalize_layout_variant("cz(qwerty)"), "cz (qwerty)")
        self.assertEqual(keyboard.normalize_layout_variant("cz ( qwerty )"), "cz (qwerty)")
        self.assertEqual(keyboard.normalize_layout_variant("cz "), "cz")
