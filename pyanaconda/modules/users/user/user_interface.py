#
# DBus interface for the user object.
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
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.namespace import get_dbus_path
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import USER


@dbus_interface(USER.interface_name)
class UserInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the user object."""

    _user_counter = 1

    @staticmethod
    def get_object_path(namespace):
        """Get the unique object path in the given namespace.

        This method is not thread safe for now.

        :param namespace: a sequence of names
        :return: a DBus path of an object
        """
        user_number = UserInterface._user_counter
        UserInterface._user_counter += 1
        return get_dbus_path(*namespace, "User", str(user_number))

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Name", self.implementation.name_changed)

    @property
    def Name(self) -> Str:
        """The name of the user."""
        return self.implementation.name

    @emits_properties_changed
    def SetName(self, name: Str):
        """Set the name of the user.

        :param name: a name
        """
        self.implementation.set_name(name)
