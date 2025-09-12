# DBus structure for ui module product data.
#
# Copyright (C) 2025 Red Hat, Inc.
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

from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["ProductData"]

class ProductData(DBusData):
    """Product runtime data to be exposed via D-Bus"""

    def __init__(self):
        self._is_final_release = False
        self._name = ""
        self._version = ""
        self._short_name = ""

    @property
    def is_final_release(self) -> Bool:
        """Whether the product is a final release.

        :return: True if final release, False otherwise.
        """
        return self._is_final_release

    @is_final_release.setter
    def is_final_release(self, value: Bool):
        self._is_final_release = value

    @property
    def name(self) -> Str:
        """The product name.

        :return: The full name of the product.
        """
        return self._name

    @name.setter
    def name(self, value: Str):
        self._name = value

    @property
    def version(self) -> Str:
        """The product version.

        :return: The version of the product.
        """
        return self._version

    @version.setter
    def version(self, value: Str):
        self._version = value

    @property
    def short_name(self) -> Str:
        """The shortened product name.

        :return: The short name of the product, e.g., "fedora" or "rhel".
        """
        return self._short_name

    @short_name.setter
    def short_name(self, value: Str):
        self._short_name = value
