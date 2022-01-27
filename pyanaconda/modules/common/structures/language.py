#
# DBus structures for the language and locale data.
#
# Copyright (C) 2022  Red Hat, Inc.  All rights reserved.
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
# You should have received the copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["LanguageData", "LocaleData"]


class LanguageData(DBusData):
    """Language data."""

    def __init__(self):
        self._english_name = ""
        self._is_common = False
        self._language_id = ""
        self._native_name = ""

    @property
    def english_name(self) -> Str:
        """English name for the language, ex: German

        :return: the english name of the language
        """
        return self._english_name

    @english_name.setter
    def english_name(self, english_name: Str):
        self._english_name = english_name

    @property
    def is_common(self) -> Bool:
        """Set if the language is common

        :return: if the language is common
        """
        return self._is_common

    @is_common.setter
    def is_common(self, is_common: Bool):
        self._is_common = is_common

    @property
    def language_id(self) -> Str:
        """Language identifier, ex: de

        :return: the language identifier
        """
        return self._language_id

    @language_id.setter
    def language_id(self, language_id: Str):
        self._language_id = language_id

    @property
    def native_name(self) -> Str:
        """Native name for the language, ex: Deutsch

        :return: the native name of the language
        """
        return self._native_name

    @native_name.setter
    def native_name(self, native_name: Str):
        self._native_name = native_name


class LocaleData(DBusData):
    """Locale data."""

    def __init__(self):
        self._english_name = ""
        self._language_id = ""
        self._locale_id = ""
        self._native_name = ""

    @property
    def english_name(self) -> Str:
        """English name for the locale, ex: German (Austria)

        :return: the english name of the locale
        """
        return self._english_name

    @english_name.setter
    def english_name(self, english_name: Str):
        self._english_name = english_name

    @property
    def language_id(self) -> Str:
        """Language identifier for the locale, ex: de

        :return: the language identifier
        """
        return self._language_id

    @language_id.setter
    def language_id(self, language_id: Str):
        self._language_id = language_id

    @property
    def locale_id(self) -> Str:
        """Locale identifier, ex: de_AT.UTF-8.

        :return: the locale identifier
        """
        return self._locale_id

    @locale_id.setter
    def locale_id(self, locale_id: Str):
        self._locale_id = locale_id

    @property
    def native_name(self) -> Str:
        """Native name for the locale, ex: Deutsch (Österreich)

        :return: the native name of the locale
        """
        return self._native_name

    @native_name.setter
    def native_name(self, native_name: Str):
        self._native_name = native_name
