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

from pyanaconda import localization
import unittest

class ParsingTests(unittest.TestCase):
    def invalid_langcodes_test(self):
        """Should return None for invalid langcodes."""

        # nonsense
        parts = localization.parse_langcode("*_&!")
        self.assertIsNone(parts)

        # no language
        parts = localization.parse_langcode("_CZ")
        self.assertIsNone(parts)

    def parsing_test(self):
        """Should correctly parse valid langcodes."""

        parts = localization.parse_langcode("cs")
        self.assertIn("language", parts)
        self.assertEqual(parts["language"], "cs")

        parts = localization.parse_langcode("cs_CZ")
        self.assertIn("language", parts)
        self.assertIn("territory", parts)
        self.assertEqual(parts["language"], "cs")
        self.assertEqual(parts["territory"], "CZ")

        parts = localization.parse_langcode("cs_CZ.UTF-8")
        self.assertIn("language", parts)
        self.assertIn("territory", parts)
        self.assertIn("encoding", parts)
        self.assertEqual(parts["language"], "cs")
        self.assertEqual(parts["territory"], "CZ")
        self.assertEqual(parts["encoding"], "UTF-8")

        parts = localization.parse_langcode("cs_CZ.UTF-8@latin")
        self.assertIn("language", parts)
        self.assertIn("territory", parts)
        self.assertIn("encoding", parts)
        self.assertIn("script", parts)
        self.assertEqual(parts["language"], "cs")
        self.assertEqual(parts["territory"], "CZ")
        self.assertEqual(parts["encoding"], "UTF-8")
        self.assertEqual(parts["script"], "latin")

        parts = localization.parse_langcode("cs.UTF-8@latin")
        self.assertIn("language", parts)
        self.assertIn("encoding", parts)
        self.assertIn("script", parts)
        self.assertEqual(parts["language"], "cs")
        self.assertEqual(parts["encoding"], "UTF-8")
        self.assertEqual(parts["script"], "latin")

        parts = localization.parse_langcode("cs_CZ@latin")
        self.assertIn("language", parts)
        self.assertIn("territory", parts)
        self.assertIn("script", parts)
        self.assertEqual(parts["language"], "cs")
        self.assertEqual(parts["territory"], "CZ")
        self.assertEqual(parts["script"], "latin")

class UpcaseFirstLetterTests(unittest.TestCase):
    def upcase_first_letter_test(self):
        """Upcasing first letter should work as expected."""

        # no change
        self.assertEqual(localization._upcase_first_letter("Czech RePuBliC"),
                         "Czech RePuBliC")

        # simple case
        self.assertEqual(localization._upcase_first_letter("czech"), "Czech")

        # first letter only
        self.assertEqual(localization._upcase_first_letter("czech republic"),
                         "Czech republic")

        # no lowercase
        self.assertEqual(localization._upcase_first_letter("czech Republic"),
                         "Czech Republic")

class ExpandLangsTest(unittest.TestCase):
    def expand_langs_test(self):
        """expand_langs should return every valid combination."""

        expected_result = ["fr", "fr_FR", "fr_FR.UTF-8@euro", "fr.UTF-8@euro",
                           "fr_FR@euro", "fr_FR.UTF-8", "fr@euro", "fr.UTF-8"]
        self.assertListEqual(localization.expand_langs("fr_FR.UTF-8@euro"),
                             expected_result)
