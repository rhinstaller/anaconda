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
import string  # pylint: disable=deprecated-module
import sys
import unicodedata


def strip_accents(s):
    """Remove diacritics from a string.

    This function takes arbitrary unicode string and returns it with all the diacritics removed.

    :param str s: arbitrary string
    :return str: s with diacritics removed
    """
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def ensure_str(str_or_bytes, keep_none=True):
    """
    Returns a str instance for given string or ``None`` if requested to keep it.

    :param str_or_bytes: string to be kept or converted to str type
    :type str_or_bytes: str or bytes
    :param bool keep_none: whether to keep None as it is or raise ValueError if
                           ``None`` is passed
    :raises ValueError: if applied on an object not being of type bytes nor str
                        (nor NoneType if ``keep_none`` is ``False``)
    """

    if keep_none and str_or_bytes is None:
        return None
    elif isinstance(str_or_bytes, str):
        return str_or_bytes
    elif isinstance(str_or_bytes, bytes):
        return str_or_bytes.decode(sys.getdefaultencoding())
    else:
        raise ValueError("str_or_bytes must be of type 'str' or 'bytes', not '%s'"
                         % type(str_or_bytes))


# Define translations between ASCII uppercase and lowercase for
# locale-independent string conversions. The tables are 256-byte string used
# with str.translate. If str.translate is used with a unicode string,
# even if the string contains only 7-bit characters, str.translate will
# raise a UnicodeDecodeError.
_ASCIIlower_table = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_ASCIIupper_table = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)


def _toASCII(s):
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


def upperASCII(s):
    """Convert a string to uppercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.

    :param str s: input string
    :return str: ascii-only uppercased value of s
    """
    s = ensure_str(s)
    return str.translate(_toASCII(s), _ASCIIupper_table)


def lowerASCII(s):
    """Convert a string to lowercase using only ASCII character definitions.

    The returned string will contain only ASCII characters. This function is
    locale-independent.

    :param str s: input string
    :return str: ascii-only lowercased value of s
    """
    s = ensure_str(s)
    return str.translate(_toASCII(s), _ASCIIlower_table)


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

    # Convert both arguments to string if not already
    str1 = ensure_str(str1)
    str2 = ensure_str(str2)

    str1 = str1.lower()
    str1_words = str1.split()
    str2 = str2.lower()

    return all(word in str2 for word in str1_words)


def decode_bytes(data):
    """Decode the given bytes.

    Return the given string or a string decoded from the given bytes.

    :param data: bytes or a string
    :return: a string
    """
    if isinstance(data, str):
        return data

    if isinstance(data, bytes):
        return data.decode('utf-8')

    raise ValueError("Unsupported type '{}'.".format(type(data).__name__))
