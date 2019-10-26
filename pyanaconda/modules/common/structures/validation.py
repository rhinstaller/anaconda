#
# DBus structures for validation.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["ValidationReport"]


class ValidationReport(DBusData):
    """The validation report."""

    def __init__(self):
        self._error_messages = []
        self._warning_messages = []

    def is_valid(self):
        """Is the validation successful?

        :return: True or False
        """
        return not self._error_messages

    def get_messages(self):
        """Get all messages.

        :return: a list of strings
        """
        return self.error_messages + self.warning_messages

    @property
    def error_messages(self) -> List[Str]:
        """List of error messages.

        :return: a list of strings
        """
        return self._error_messages

    @error_messages.setter
    def error_messages(self, messages: List[Str]):
        self._error_messages = list(messages)

    @property
    def warning_messages(self) -> List[Str]:
        """List of warning messages.

        :return: a list of strings
        """
        return self._warning_messages

    @warning_messages.setter
    def warning_messages(self, messages: List[Str]):
        self._warning_messages = list(messages)
