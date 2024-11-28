#
# DBus structure for comps definitions.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["CompsEnvironmentData", "CompsGroupData"]


class CompsGroupData(DBusData):
    """Comps group data."""

    def __init__(self):
        self._id = ""
        self._name = ""
        self._description = ""

    @property
    def id(self) -> Str:
        """Unique identifier of the group.

        :return: a string
        """
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self) -> Str:
        """Translated name of the group.

        :return: a translated string
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def description(self) -> Str:
        """Translated description of the group.

        :return: a translated string
        """
        return self._description

    @description.setter
    def description(self, value):
        self._description = value


class CompsEnvironmentData(DBusData):
    """Comps environment data."""

    def __init__(self):
        self._id = ""
        self._name = ""
        self._description = ""
        self._optional_groups = []
        self._default_groups = []
        self._visible_groups = []

    @property
    def id(self) -> Str:
        """Unique identifier of the environment.

        :return: a string
        """
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self) -> Str:
        """Translated name of the environment.

        :return: a translated string
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def description(self) -> Str:
        """Translated description of the environment.

        :return: a translated string
        """
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def optional_groups(self) -> List[Str]:
        """List of optional groups.

        These groups don't have to be installed for
        successful installation of the environment.

        :return: a list of group identifiers
        """
        return self._optional_groups

    @optional_groups.setter
    def optional_groups(self, value):
        self._optional_groups = value

    @property
    def default_groups(self) -> List[Str]:
        """List of default optional groups.

        These groups don't have to be installed for
        successful installation of the environment,
        but they will be pre-selected by default.

        :return: a list of group identifiers
        """
        return self._default_groups

    @default_groups.setter
    def default_groups(self, value):
        self._default_groups = value

    @property
    def visible_groups(self) -> List[Str]:
        """List of user-visible groups.

        These groups are not defined by the environment,
        but they supplement the list of optional groups
        that can be selected by users.

        :return: a list of group identifiers
        """
        return self._visible_groups

    @visible_groups.setter
    def visible_groups(self, value):
        self._visible_groups = value

    def get_available_groups(self) -> List[Str]:
        """Get a list of groups available for the user selection.

        :return: a list of group identifiers
        """
        return list(dict.fromkeys(
            self.optional_groups
            + self.default_groups
            + self.visible_groups
        ))
