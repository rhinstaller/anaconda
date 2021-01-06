#
# Copyright (C) 2021 Red Hat, Inc.
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

__all__ = ["context"]

from pyanaconda.anaconda import Anaconda


class UserInterfaceContext(object):
    """The context of the user interface.

    The context provides access to persistent objects
    of the user interface. The goal is to replace all
    these objects with this one.

    We might replace this object with a DBus module in
    the future.
    """

    def __init__(self):
        self._anaconda = Anaconda()

    @property
    def anaconda(self) -> Anaconda:
        """The Anaconda object."""
        return self._anaconda

    @property
    def data(self):
        """The kickstart data."""
        return self._anaconda.ksdata

    @property
    def payload(self):
        """The payload object."""
        return self._anaconda.payload


context = UserInterfaceContext()
