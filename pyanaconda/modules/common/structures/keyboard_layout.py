#
# DBus structure for keyboard layout in localization module.
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
#
from dasbus.structure import DBusData
from dasbus.typing import List, Str  # Pylint: disable=wildcard-import

__all__ = ["KeyboardLayout"]


class KeyboardLayout(DBusData):
    """Structure representing a keyboard layout."""

    def __init__(self):
        self._layout_id = ""
        self._description = ""
        self._supports_ascii = False
        self._is_common = False
        self._langs = []

    @property
    def layout_id(self) -> Str:
        """Return the keyboard layout ID."""
        return self._layout_id

    @layout_id.setter
    def layout_id(self, value: Str):
        self._layout_id = value

    @property
    def description(self) -> Str:
        """Return the description of the layout."""
        return self._description

    @description.setter
    def description(self, value: Str):
        self._description = value

    @property
    def is_common(self) -> bool:
        """Return whether the layout is common."""
        return self._is_common

    @is_common.setter
    def is_common(self, value: bool):
        self._is_common = value

    @property
    def supports_ascii(self) -> bool:
        """Return whether the layout is capable of typing ASCII characters."""
        return self._supports_ascii

    @supports_ascii.setter
    def supports_ascii(self, value: bool):
        self._supports_ascii = value

    @property
    def langs(self) -> List[Str]:
        """Return the list of associated languages."""
        return self._langs

    @langs.setter
    def langs(self, value: List[Str]):
        self._langs = value

    def __eq__(self, other):
        """Ensure KeyboardLayout objects are correctly compared."""
        if isinstance(other, KeyboardLayout):
            return (
                    self.layout_id == other.layout_id
                    and self.description == other.description
                    and self.langs == other.langs
            )
        return False
