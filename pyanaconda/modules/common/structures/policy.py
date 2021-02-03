#
# DBus structures for the password policy.
#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf

log = get_module_logger(__name__)

__all__ = ["PasswordPolicy"]


class PasswordPolicy(DBusData):
    """The password policy data."""

    def __init__(self):
        self._min_quality = UInt16(0)
        self._min_length = UInt16(0)
        self._allow_empty = True
        self._is_strict = False

    @property
    def min_quality(self) -> UInt16:
        """The minimum quality score (see libpwquality).

        :return: a number from 0 to 100
        """
        return self._min_quality

    @min_quality.setter
    def min_quality(self, value):
        self._min_quality = UInt16(value)

    @property
    def min_length(self) -> UInt16:
        """The minimum length of the password..

        :return: a number of characters
        """
        return self._min_length

    @min_length.setter
    def min_length(self, value):
        self._min_length = UInt16(value)

    @property
    def allow_empty(self) -> Bool:
        """Should an empty password be allowed?

        :return: True or False
        """
        return self._allow_empty

    @allow_empty.setter
    def allow_empty(self, value: Bool):
        self._allow_empty = value

    @property
    def is_strict(self) -> Bool:
        """Should the minimal quality be required?

        :return: True or False
        """
        return self._is_strict

    @is_strict.setter
    def is_strict(self, value: Bool):
        self._is_strict = value

    @classmethod
    def from_defaults(cls, policy_name):
        """Create a default policy.

        :param policy_name: a name of the policy
        :return: a new instance of PasswordPolicy
        """
        policy = cls()

        for attrs in conf.ui.password_policies:
            if policy_name != attrs.get("name"):
                continue

            policy.min_quality = attrs.get("quality")
            policy.min_length = attrs.get("length")
            policy.allow_empty = attrs.get("empty", False)
            policy.is_strict = attrs.get("strict", False)
            break
        else:
            log.debug(
                "No default %s password policy is "
                "configured.", policy_name
            )

        return policy

    @classmethod
    def to_structure_dict(cls, objects) -> Dict[Str, Structure]:
        """Convert password policies to DBus structures.

        :param objects: a dictionary of policy names and policy data objects
        :return: a dictionary of policy names and DBus structures
        """
        if not isinstance(objects, dict):
            raise TypeError(
                "Invalid type '{}'.".format(type(objects).__name__)
            )

        return {k: PasswordPolicy.to_structure(v) for k, v in objects.items()}

    @classmethod
    def from_structure_dict(cls, structures: Dict[Str, Structure]):
        """Convert DBus structures to password policies.

        :param structures: a dictionary of policy names and DBus structures
        :return: a dictionary of policy names and policy data objects
        """
        if not isinstance(structures, dict):
            raise TypeError(
                "Invalid type '{}'.".format(type(structures).__name__)
            )

        return {k: PasswordPolicy.from_structure(v) for k, v in structures.items()}
