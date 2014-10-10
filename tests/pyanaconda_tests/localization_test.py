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
from pyanaconda.iutil import execReadlines
import locale as locale_mod
import unittest

class ParsingTests(unittest.TestCase):
    def invalid_langcodes_test(self):
        """Should return None for invalid langcodes."""

        # None
        parts = localization.parse_langcode(None)
        self.assertIsNone(parts)

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

class LangcodeLocaleMatchingTests(unittest.TestCase):
    def langcode_matches_locale_test(self):
        """Langcode-locale matching should work as expected."""

        # should match
        self.assertTrue(localization.langcode_matches_locale("sr", "sr"))
        self.assertTrue(localization.langcode_matches_locale("sr", "sr_RS"))
        self.assertTrue(localization.langcode_matches_locale("sr", "sr_RS.UTF-8"))
        self.assertTrue(localization.langcode_matches_locale("sr", "sr_RS.UTF-8@latin"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS", "sr_RS"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS", "sr_RS.UTF-8"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS", "sr_RS.UTF-8@latin"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS.UTF-8", "sr_RS.UTF-8"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS.UTF-8", "sr_RS.UTF-8@latin"))
        self.assertTrue(localization.langcode_matches_locale("sr_RS.UTF-8@latin", "sr_RS.UTF-8@latin"))

        # missing language, shouldn't match
        self.assertFalse(localization.langcode_matches_locale("", "sr"))
        self.assertFalse(localization.langcode_matches_locale("sr", ""))
        self.assertFalse(localization.langcode_matches_locale("sr", None))
        self.assertFalse(localization.langcode_matches_locale(None, "sr"))

        # missing items in the locale, shouldn't match
        self.assertFalse(localization.langcode_matches_locale("sr_RS", "sr"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS.UTF-8", "sr_RS"))
        self.assertFalse(localization.langcode_matches_locale("sr.UTF-8", "sr_RS"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS.UTF-8", "sr.UTF-8"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS.UTF-8@latin", "sr_RS"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS@latin", "sr_RS"))
        self.assertFalse(localization.langcode_matches_locale("sr.UTF-8@latin", "sr_RS.UTF-8"))
        self.assertFalse(localization.langcode_matches_locale("sr@latin", "sr_RS"))

        # different parts, shouldn't match
        self.assertFalse(localization.langcode_matches_locale("sr", "en"))
        self.assertFalse(localization.langcode_matches_locale("de_CH", "fr_CH"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS", "sr_ME"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS@latin", "sr_RS@cyrilic"))
        self.assertFalse(localization.langcode_matches_locale("sr_RS@latin", "sr_ME@latin"))

    def find_best_locale_match_test(self):
        """Finding best locale matches should work as expected."""

        # can find best matches
        self.assertEqual(localization.find_best_locale_match("cs_CZ", ["cs", "cs_CZ", "en", "en_US"]), "cs_CZ")
        self.assertEqual(localization.find_best_locale_match("cs", ["cs_CZ", "cs", "en", "en_US"]), "cs")
        self.assertEqual(localization.find_best_locale_match("pt_BR", ["pt", "pt_BR"]), "pt_BR")
        self.assertEqual(localization.find_best_locale_match("pt_BR", ["pt", "pt_BR", "pt_PT"]), "pt_BR")
        self.assertEqual(localization.find_best_locale_match("cs_CZ.UTF-8", ["cs", "cs_CZ", "cs_CZ.UTF-8"]),
                         "cs_CZ.UTF-8")
        self.assertEqual(localization.find_best_locale_match("cs_CZ.UTF-8@latin",
                                                             ["cs", "cs_CZ@latin", "cs_CZ.UTF-8"]), "cs_CZ@latin")

        # no matches
        self.assertIsNone(localization.find_best_locale_match("pt_BR", ["en_BR", "en"]))
        self.assertIsNone(localization.find_best_locale_match("cs_CZ.UTF-8", ["en", "en.UTF-8"]))

    def resolve_date_format_test(self):
        """All locales' date formats should be properly resolved."""

        locales = (line.strip() for line in execReadlines("locale", ["-a"]))
        for locale in locales:
            try:
                locale_mod.setlocale(locale_mod.LC_ALL, locale)
            except locale_mod.Error:
                # cannot set locale (a bug in the locale module?)
                continue

            order = localization.resolve_date_format(1, 2, 3, fail_safe=False)[0]
            for i in (1, 2, 3):
                self.assertIn(i, order)
