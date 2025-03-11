# -*- coding: utf-8 -*-
#
# Copyright (C) 2021  Red Hat, Inc.
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

import unittest

from pyanaconda.core.string import (
    _to_ascii,
    have_word_match,
    lower_ascii,
    split_in_two,
    strip_accents,
    upcase_first_letter,
    upper_ascii,
)


class UpcaseFirstLetterTests(unittest.TestCase):
    """Tests for upcase_first_letter."""

    def test_upcase_first_letter(self):
        """Upcasing first letter should work as expected."""

        # no change
        assert upcase_first_letter("Czech RePuBliC") == "Czech RePuBliC"

        # simple case
        assert upcase_first_letter("czech") == "Czech"

        # first letter only
        assert upcase_first_letter("czech republic") == "Czech republic"

        # no lowercase
        assert upcase_first_letter("czech Republic") == "Czech Republic"

        # just one letter
        assert upcase_first_letter("q") == "Q"

        # empty string
        assert upcase_first_letter("") == ""


class StripAccentsTests(unittest.TestCase):
    """Tests for strip_accents."""

    def test_strip_accents_empty(self):
        """Test strip_accents - empty string."""
        assert strip_accents("") == ""

    def test_strip_accents_czech(self):
        """Test strip_accents - Czech accents."""
        assert strip_accents("ěščřžýáíéúů") == "escrzyaieuu"
        assert strip_accents("v češtině") == "v cestine"
        assert strip_accents("měšťánek rozšíří HÁČKY") == "mestanek rozsiri HACKY"
        assert strip_accents("nejneobhospodařovávatelnějšímu") == \
            "nejneobhospodarovavatelnejsimu"

    def test_strip_accents_german(self):
        """Test strip_accents - German umlauts."""
        assert strip_accents("Lärmüberhörer") == "Larmuberhorer"
        assert strip_accents("Heizölrückstoßabdämpfung") == \
            "Heizolrucksto\xdfabdampfung"

    def test_strip_accents_japanese(self):
        """Test strip_accents - Japanese."""
        assert strip_accents("日本語") == "\u65e5\u672c\u8a9e"
        assert strip_accents("アナコンダ") == "\u30a2\u30ca\u30b3\u30f3\u30bf"  # Anaconda

    def test_strip_accents_combined(self):
        """Test strip_accents - combined."""
        input_string = "ASCI měšťánek アナコンダ Heizölrückstoßabdämpfung"
        output_string = "ASCI mestanek \u30a2\u30ca\u30b3\u30f3\u30bf Heizolrucksto\xdfabdampfung"
        assert strip_accents(input_string) == output_string


class AsciiConversionTests(unittest.TestCase):
    """Tests for the group of ASCII conversion functions."""

    def test_to_ascii_str(self):
        """Test _to_ascii str conversions."""
        assert _to_ascii("") == ""
        assert _to_ascii(" ") == " "
        assert _to_ascii("&@`'łŁ!@#$%^&*{}[]$'<>*") == \
            "&@`'!@#$%^&*{}[]$'<>*"
        assert _to_ascii("ABC") == "ABC"
        assert _to_ascii("aBC") == "aBC"
        _out = "Heizolruckstoabdampfung"
        assert _to_ascii("Heizölrückstoßabdämpfung") == _out

    def test_to_ascii_bytes(self):
        """Test _to_ascii bytes handling."""
        in_bytes = b"bytes"
        output = _to_ascii(in_bytes)
        assert in_bytes == output
        assert id(in_bytes) == id(output)

    def test_to_ascii_other(self):
        """Test _to_ascii handling of other types."""
        assert _to_ascii(None) == ""
        assert _to_ascii(132456) == ""

    def test_upper_ascii(self):
        """Test upper_ascii."""
        assert upper_ascii("") == ""
        assert upper_ascii("a") == "A"
        assert upper_ascii("A") == "A"
        assert upper_ascii("aBc") == "ABC"
        assert upper_ascii("_&*'@#$%^aBcžčŘ") == \
            "_&*'@#$%^ABCZCR"
        _out = "HEIZOLRUCKSTOABDAMPFUNG"
        assert upper_ascii("Heizölrückstoßabdämpfung") == _out

    def test_lower_ascii(self):
        """Test lower_ascii."""
        assert lower_ascii("") == ""
        assert lower_ascii("A") == "a"
        assert lower_ascii("a") == "a"
        assert lower_ascii("aBc") == "abc"
        assert lower_ascii("_&*'@#$%^aBcžčŘ") == \
            "_&*'@#$%^abczcr"
        _out = "heizolruckstoabdampfung"
        assert lower_ascii("Heizölrückstoßabdämpfung") == _out


class HaveWordMatchTests(unittest.TestCase):
    """Tests for have_word_match"""

    def test_have_word_match_positive(self):
        """Test have_word_match positive results."""
        assert have_word_match("word1 word2", "word1 word2 word3")
        assert have_word_match("word1 word2", "word2 word1 word3")
        assert have_word_match("word2 word1", "word3 word1 word2")
        assert have_word_match("word1", "word1 word2")
        assert have_word_match("word1 word2", "word2word1 word3")
        assert have_word_match("word2 word1", "word3 word1word2")
        assert have_word_match("word1", "word1word2")
        assert have_word_match("", "word1")

    def test_have_word_match_negative(self):
        """Test have_word_match negative results."""
        assert not have_word_match("word3 word1", "word1")
        assert not have_word_match("word1 word3", "word1 word2")
        assert not have_word_match("word3 word2", "word1 word2")
        assert not have_word_match("word1word2", "word1 word2 word3")
        assert not have_word_match("word1", "")
        assert not have_word_match("word1", None)
        assert not have_word_match(None, "word1")
        assert not have_word_match("", None)
        assert not have_word_match(None, "")
        assert not have_word_match(None, None)

    def test_have_word_match_unicode(self):
        """Test have_word_match with unicode.

        Compare designated unicode and "standard" unicode string and make sure nothing crashes.
        """
        assert have_word_match("fête", "fête champêtre")
        assert have_word_match("fête", "fête champêtre")


class SplitInTwoTests(unittest.TestCase):
    """Tests for split_in_two."""

    def test_split_in_two_whitespace(self):
        """Test the split_in_two function with whitespaces."""
        assert split_in_two("") == ("", "")
        assert split_in_two("a") == ("a", "")
        assert split_in_two("a ") == ("a", "")
        assert split_in_two("a  ") == ("a", "")
        assert split_in_two("a  b") == ("a", "b")
        assert split_in_two("a  b ") == ("a", "b ")
        assert split_in_two("a  b  c") == ("a", "b  c")
        assert split_in_two("a  b  c ") == ("a", "b  c ")

    def test_split_in_two_delimiter(self):
        """Test the split_in_two function with a special delimiter."""
        assert split_in_two("", delimiter=":") == ("", "")
        assert split_in_two(":", delimiter=":") == ("", "")
        assert split_in_two("a", delimiter=":") == ("a", "")
        assert split_in_two("a:", delimiter=":") == ("a", "")
        assert split_in_two("a:b", delimiter=":") == ("a", "b")
        assert split_in_two("a:b", delimiter=":") == ("a", "b")
        assert split_in_two("a:b:", delimiter=":") == ("a", "b:")
        assert split_in_two("a:b:c", delimiter=":") == ("a", "b:c")
        assert split_in_two("a:b:c:", delimiter=":") == ("a", "b:c:")
