#
# DBus structures for the realm data.
#
# Copyright (C) 2018  Red Hat, Inc.  All rights reserved.
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

__all__ = ["RealmData"]


class RealmData(DBusData):
    """Realm data."""

    def __init__(self):
        self._name = ""
        self._discover_options = []
        self._join_options = []
        self._discovered = False
        self._required_packages = []

    @property
    def name(self) -> Str:
        """Specification of the realm to join."

        For example: 'domain.example.com'

        :return: a name of the realm
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def discover_options(self) -> List[Str]:
        """Options for the discovery command.

        For example: ['--client-software=sssd']

        :return: a list of options
        """
        return self._discover_options

    @discover_options.setter
    def discover_options(self, options: List[Str]):
        self._discover_options = options

    @property
    def join_options(self) -> List[Str]:
        """Options for the join command.

        For example: ['--no-password', '--client-software=sssd']

        :return: a list of options
        """
        return self._join_options

    @join_options.setter
    def join_options(self, options: List[Str]):
        self._join_options = options

    @property
    def discovered(self) -> Bool:
        """Reports if a realm has been successfully discovered."""
        return self._discovered

    @discovered.setter
    def discovered(self, discovered: Bool):
        self._discovered = discovered

    @property
    def required_packages(self) -> List[Str]:
        """Packages required for joining a realm.

        For example: ['realmd']

        :return: a list of required packages
        """
        return self._required_packages

    @required_packages.setter
    def required_packages(self, packages: List[Str]):
        self._required_packages = packages
