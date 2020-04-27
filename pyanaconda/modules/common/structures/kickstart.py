#
# DBus structures for kickstart.
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

__all__ = ["KickstartMessage", "KickstartReport"]


class KickstartMessage(DBusData):
    """The kickstart message."""

    def __init__(self):
        self._module_name = ""
        self._file_name = ""
        self._line_number = 0
        self._message = ""

    @property
    def module_name(self) -> Str:
        """Name of the DBus module.

        :return: a DBus name
        """
        return self._module_name

    @module_name.setter
    def module_name(self, value: Str):
        self._module_name = value

    @property
    def file_name(self) -> Str:
        """Name of the file.

        :return: a file name
        """
        return self._file_name

    @file_name.setter
    def file_name(self, value: Str):
        self._file_name = value

    @property
    def line_number(self) -> UInt32:
        """Number of the line.

        :return: a number
        """
        return UInt32(self._line_number)

    @line_number.setter
    def line_number(self, value: UInt32):
        self._line_number = value

    @property
    def message(self) -> Str:
        """Translated message.

        :return: a string
        """
        return self._message

    @message.setter
    def message(self, value: Str):
        self._message = value

    @classmethod
    def for_error(cls, e):
        """Create a new message for a kickstart error.

        :param e: an instance of KickstartError
        :return: an instance of KickstartMessage
        """
        data = cls()
        data.message = e.message
        data.line_number = e.lineno or 0
        return data

    @classmethod
    def for_warning(cls, warn_msg):
        """Create a new message for a kickstart error.

        :param str warn_msg: a warning string
        :return: an instance of KickstartMessage
        """
        data = cls()
        data.message = warn_msg
        data.line_number = 0
        return data

    def __str__(self):
        """Return the string representation."""
        return self.message


class KickstartReport(DBusData):
    """The kickstart report."""

    def __init__(self):
        self._error_messages = []
        self._warning_messages = []

    def is_valid(self):
        """Is the kickstart valid?

        :return: True or False
        """
        return not self._error_messages

    def get_messages(self):
        """Get all messages.

        :return: a list of messages
        """
        return self.error_messages + self.warning_messages

    @property
    def error_messages(self) -> List[KickstartMessage]:
        """List of error messages.

        :return: a list of messages
        """
        return self._error_messages

    @error_messages.setter
    def error_messages(self, messages: List[KickstartMessage]):
        self._error_messages = list(messages)

    @property
    def warning_messages(self) -> List[KickstartMessage]:
        """List of warning messages.

        :return: a list of messages
        """
        return self._warning_messages

    @warning_messages.setter
    def warning_messages(self, messages: List[KickstartMessage]):
        self._warning_messages = list(messages)
