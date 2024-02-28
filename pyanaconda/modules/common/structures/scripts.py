#
# DBus structures for the packages data.
#
# Copyright (C) 2024 Red Hat, Inc.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

class Script(DBusData):
    """ Structure for the script data. """

    def __init__(self, _type: Int, script: Str, interp: Str, logfile: Str, errorOnFail: Bool, lineno: Int):
        self.type = _type
        self.script = script
        self.interp = interp
        self.logfile = logfile
        self.errorOnFail = errorOnFail
        self.lineno = lineno

    @property
    def type(self) -> Int:
        """ The type of the script.

        :return: The type of the script.
        :rtype: Int
        """
        return self.type

    @type.setter
    def type(self, value: Int) -> None:
        self.type = value

    @property
    def script(self) -> Str:
        """ The script.

        :return: The script.
        :rtype: Str
        """
        return self.script

    @script.setter
    def script(self, value: Str) -> None:
        self.script = value
