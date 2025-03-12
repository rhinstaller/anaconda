#
# DBus structures for secret data.
#
# Copyright (C) 2020 Red Hat, Inc.
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
#
import copy

from dasbus.structure import DBusData, generate_string_from_data, get_fields
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    SECRET_TYPE_HIDDEN,
    SECRET_TYPE_NONE,
    SECRET_TYPE_TEXT,
)

log = get_module_logger(__name__)

__all__ = ["SecretData", "SecretDataList", "get_public_copy", "hide_secrets"]


def get_public_copy(obj: DBusData):
    """Get a public copy of the given DBus data object.

    The function will create a copy of the given DBus
    data object, automatically detect all fields that
    are instances of SecretData and call their method
    hide_secret.

    The final DBus data object is safe to send to a DBus
    client, because it doesn't contain sensitive information.

    The automatic detection works only for first-level
    fields of the type SecretData. Nested types of fields
    are not supported at this moment. For example, a field
    of the type List[SecretData] will be ignored. We will
    also ignore types that are subclasses of DBusData (with
    the exception of SecretData).

    FIXME: Add support for nested types of fields.

    :param obj: a data object with secrets
    :type obj: an instance of DBusData
    :return: a copy of data object with hidden secrets
    :rtype: an instance of DBusData
    """
    obj = copy.deepcopy(obj)
    hide_secrets(obj)
    return obj


def hide_secrets(obj: DBusData):
    """Hide all secrets in the given DBus data object.

    The function will search fields of the given
    DBus data object, check if the value of a field
    is an instance of SecretData and call its method
    hide_secret.

    :param obj: a data object with secrets
    :type obj: an instance of DBusData
    """
    fields = get_fields(obj)
    hidden = []

    for field in fields.values():
        value = getattr(obj, field.data_name)

        if isinstance(value, SecretData):
            value.hide_secret()
            hidden.append(field.name)

    if hidden:
        log.debug("Hiding DBus fields %s.", ", ".join(hidden))


class SecretData(DBusData):
    """Data for a secret string value."""

    def __init__(self):
        self._type = SECRET_TYPE_NONE
        self._value = self._get_initial_value()

    @property
    def type(self) -> Str:
        """The type of the secret.

        Supported values:
            NONE    The secret is not set.
            HIDDEN  The secret is hidden.
            TEXT    The secret is in plain text.

        :return: a string
        """
        return self._type

    @type.setter
    def type(self, value: Str):
        self._type = value

    @property
    def value(self) -> Str:
        """The value of the secret.

        The value is set only if the secret
        is set and not hidden.

        :return: a string
        """
        return self._value

    @value.setter
    def value(self, value: Str):
        self._value = value

    def _get_initial_value(self) -> Str:
        """Get the initial value of the secret.

        :return: a value
        """
        return ""

    def set_secret(self, value):
        """Set the secret.

        If the value is None, clear the secret. Otherwise,
        set the secret to the given value.

        :param value: a value of the secret or None
        """
        if value is None:
            self.type = SECRET_TYPE_NONE
            self.value = self._get_initial_value()
        else:
            self.type = SECRET_TYPE_TEXT
            self.value = value

    def hide_secret(self):
        """Hide the secret.

        If the secret is not set, do nothing. Otherwise,
        hide the value of the secret.
        """
        if self.type == SECRET_TYPE_NONE:
            self.value = self._get_initial_value()
        else:
            self.type = SECRET_TYPE_HIDDEN
            self.value = self._get_initial_value()

    def __repr__(self):
        """Convert this data object to a string."""
        return generate_string_from_data(
            self, skip=["value"], add={"value_set": bool(self.value)}
        )


class SecretDataList(SecretData):
    """Data for a secret list of string values."""

    @property
    def value(self) -> List[Str]:
        """The value of the secret.

        :return: a list of strings
        """
        return self._value

    @value.setter
    def value(self, value: List[Str]):
        self._value = value

    def _get_initial_value(self) -> List[Str]:
        """Get the initial value of the secret.

        :return: a value
        """
        return []
