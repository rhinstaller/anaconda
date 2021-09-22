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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.

import unittest
import pytest

from pyanaconda.core.string import strip_accents, upcase_first_letter, _toASCII, upperASCII, \
    lowerASCII, have_word_match, decode_bytes


class UpcaseFirstLetterTests(unittest.TestCase):

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


class MiscTests(unittest.TestCase):

    def test_strip_accents(self):
        """Test strip_accents."""

        # empty string
        assert strip_accents("") == ""

        # some Czech accents
        assert strip_accents("ěščřžýáíéúů") == "escrzyaieuu"
        assert strip_accents("v češtině") == "v cestine"
        assert strip_accents("měšťánek rozšíří HÁČKY") == "mestanek rozsiri HACKY"
        assert strip_accents("nejneobhospodařovávatelnějšímu") == \
            "nejneobhospodarovavatelnejsimu"

        # some German umlauts
        assert strip_accents("Lärmüberhörer") == "Larmuberhorer"
        assert strip_accents("Heizölrückstoßabdämpfung") == \
            "Heizolrucksto\xdfabdampfung"

        # some Japanese
        assert strip_accents("日本語") == "\u65e5\u672c\u8a9e"
        assert strip_accents("アナコンダ") == "\u30a2\u30ca\u30b3\u30f3\u30bf"  # Anaconda

        # combined
        input_string = "ASCI měšťánek アナコンダ Heizölrückstoßabdämpfung"
        output_string = "ASCI mestanek \u30a2\u30ca\u30b3\u30f3\u30bf Heizolrucksto\xdfabdampfung"
        assert strip_accents(input_string) == output_string

    def test_to_ascii(self):
        """Test _toASCII."""

        # check some conversions
        assert _toASCII("") == ""
        assert _toASCII(" ") == " "
        assert _toASCII("&@`'łŁ!@#$%^&*{}[]$'<>*") == \
            "&@`'!@#$%^&*{}[]$'<>*"
        assert _toASCII("ABC") == "ABC"
        assert _toASCII("aBC") == "aBC"
        _out = "Heizolruckstoabdampfung"
        assert _toASCII("Heizölrückstoßabdämpfung") == _out

    def test_upper_ascii(self):
        """Test upperASCII."""

        assert upperASCII("") == ""
        assert upperASCII("a") == "A"
        assert upperASCII("A") == "A"
        assert upperASCII("aBc") == "ABC"
        assert upperASCII("_&*'@#$%^aBcžčŘ") == \
            "_&*'@#$%^ABCZCR"
        _out = "HEIZOLRUCKSTOABDAMPFUNG"
        assert upperASCII("Heizölrückstoßabdämpfung") == _out

    def test_lower_ascii(self):
        """Test lowerASCII."""
        assert lowerASCII("") == ""
        assert lowerASCII("A") == "a"
        assert lowerASCII("a") == "a"
        assert lowerASCII("aBc") == "abc"
        assert lowerASCII("_&*'@#$%^aBcžčŘ") == \
            "_&*'@#$%^abczcr"
        _out = "heizolruckstoabdampfung"
        assert lowerASCII("Heizölrückstoßabdämpfung") == _out

    def test_have_word_match(self):
        """Test have_word_match."""

        assert have_word_match("word1 word2", "word1 word2 word3")
        assert have_word_match("word1 word2", "word2 word1 word3")
        assert have_word_match("word2 word1", "word3 word1 word2")
        assert have_word_match("word1", "word1 word2")
        assert have_word_match("word1 word2", "word2word1 word3")
        assert have_word_match("word2 word1", "word3 word1word2")
        assert have_word_match("word1", "word1word2")
        assert have_word_match("", "word1")

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

        # Compare designated unicode and "standard" unicode string and make sure nothing crashes
        assert have_word_match("fête", "fête champêtre")
        assert have_word_match("fête", "fête champêtre")

    def test_decode_bytes(self):
        assert "STRING" == decode_bytes("STRING")
        assert "BYTES" == decode_bytes(b"BYTES")
        with pytest.raises(ValueError):
            decode_bytes(None)
        with pytest.raises(ValueError):
            decode_bytes(0)
        with pytest.raises(ValueError):
            decode_bytes([])
