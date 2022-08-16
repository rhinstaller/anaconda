#
# string.py - generic string utility functions
#
# Copyright (C) 2021  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import string
import unicodedata


def strip_accents(s):
    """Remove diacritics from a string.

    This function takes arbitrary unicode string and returns it with all the diacritics removed.

    :param str s: arbitrary string
    :return str: s with diacritics removed
    """
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


# Define translations between ASCII uppercase and lowercase for
# locale-independent string conversions. The tables are 256-byte string used
# with str.translate. If str.translate is used with a unicode string,
# even if the string contains only 7-bit characters, str.translate will
# raise a UnicodeDecodeError.
_ascii_lower_table = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_ascii_upper_table = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)


def _to_ascii(s):
    """Convert a unicode string to ASCII

    :param str s: input string
    :return str: string with only ASCII characters
    """
    if isinstance(s, str):
        # Decompose the string using the NFK decomposition, which in addition
        # to the canonical decomposition replaces characters based on
        # compatibility equivalence (e.g., ROMAN NUMERAL ONE has its own code
        # point but it's really just a capital I), so that we can keep as much
        # of the ASCII part of the string as possible.
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode("ascii")
    elif not isinstance(s, bytes):
        s = ''
    return s


def upper_ascii(s):
    """Convert a string to uppercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.

    :param str s: input string
    :return str: ascii-only uppercased value of s
    """
    return str.translate(_to_ascii(s), _ascii_upper_table)


def lower_ascii(s):
    """Convert a string to lowercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.

    :param str s: input string
    :return str: ascii-only lowercased value of s
    """
    return str.translate(_to_ascii(s), _ascii_lower_table)


def upcase_first_letter(text):
    """Upcase first letter of a string.

    Helper function that upcases the first letter of the string. Python's
    standard string.capitalize() not only upcases the first letter but also
    lowercases all the others. string.title() capitalizes all words in the
    string.

    Note: Never use on translated strings!

    :param str text: text to upcase
    :return str: the given text with the first letter upcased
    """

    if not text:
        # cannot change anything
        return text
    elif len(text) == 1:
        return text.upper()
    else:
        return text[0].upper() + text[1:]


def have_word_match(str1, str2):
    """Tells if all words from str1 exist in str2 or not.

    :param str str1: list of words to look for
    :param str str2: list of words to search in
    :return bool: does str2 contain all the words from str1
    """

    if str1 is None or str2 is None:
        # None never matches
        return False

    if str1 == "":
        # empty string matches everything except from None
        return True

    if str2 == "":
        # non-empty string cannot be found in an empty string
        return False

    str1 = str1.lower()
    str1_words = str1.split()
    str2 = str2.lower()

    return all(word in str2 for word in str1_words)


def split_in_two(text, delimiter=None):
    """Split the given string into two strings.

    This function is useful for safe tuple unpacking.
    The functionality is similar to str.partition(),
    but it supports the delimiter of str.split().

    If the delimiter is None, the string is split by
    a group of whitespace characters that are treated
    as a single separator.

    For example:

        first, second = split_in_two(text)

    :param text: a string to split
    :param delimiter: a delimiter for splitting
    :return: a tuple of exactly two strings
    """
    # There might be up to two items in the list.
    items = iter(text.split(sep=delimiter, maxsplit=1))

    # Return exactly two items. Use empty strings as defaults.
    return next(items, ""), next(items, "")
