#
# DBus structures for the payload data.
#
# Copyright (C) 2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.dbus.structure import DBusData
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import


class Requirement(DBusData):
    """An object to store a payload requirement with info about its reasons.

    For each requirement multiple reasons together with their strength
    can be stored in this object using the add_reason method.
    A reason should be just a string with description (ie for tracking purposes).
    Strength is a boolean flag that can be used to indicate whether missing the
    requirement should be considered fatal. Strength of the requirement is
    given by strength of all its reasons.
    """
    def __init__(self):
        self._id = None
        self._reasons = []
        self._strong = False

    @property
    def id(self) -> Str:
        """Identifier of the requirement (eg. a package name)"""
        return self._id

    @id.setter
    def id(self, req_id: Str):
        """Set identifier of the requirement (eg. a package name)"""
        self._id = req_id

    @property
    def reasons(self) -> List[Str]:
        """List of reasons for the requirement"""
        return self._reasons

    @reasons.setter
    def reasons(self, reasons: List[Str]):
        """Set list of reasons for this requirement"""
        self._reasons = reasons

    @property
    def strong(self) -> Bool:
        """Strength of the requirement (ie. should it be considered fatal?)"""
        return self._strong

    @strong.setter
    def strong(self, strong: Bool):
        """Set strength of the requirement (ie. should it be considered fatal?)"""
        self._strong = strong

    def add_reason(self, reason, strong=False):
        """Adds a reason to the requirement with optional strength of the reason

        :param reason: add a new reason for this requirement
        :type reason: string
        :param strong: set if this reason is a strong requirement
        :type strong: bool
        """
        if not self._strong and strong:
            self._strong = True

        self._reasons.append(reason)

    def __str__(self):
        return "PayloadRequirement(id=%s, reasons=%s, strong=%s)" % (self.id,
                                                                     self.reasons,
                                                                     self.strong)

    def __repr__(self):
        return 'PayloadRequirement(id=%s, reasons=%s)' % (self.id, self._reasons)
