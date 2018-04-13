#
# DBus interface for the users module.
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

from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(USERS.interface_name)
class UsersInterface(KickstartModuleInterface):
    """DBus interface for Users module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.root_password_is_set_changed.connect(self.changed("IsRootPasswordSet"))
        self.implementation.root_account_locked_changed.connect(self.changed("IsRootAccountLocked"))
        self.implementation.rootpw_seen_changed.connect(self.changed("IsRootpwKickstarted"))

    @property
    def IsRootpwKickstarted(self) -> Bool:
        """Was the rootpw command seen in kickstart ?

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can report
              if the password changed from kickstart

        :return: True, if the rootpw was present in input kickstart, otherwise False
        """
        return self.implementation.rootpw_seen

    @emits_properties_changed
    def SetRootpwKickstarted(self, rootpw_seen: Bool):
        """Set if rootpw should be considered as coming from kickstart.

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can report
              if the password changed from kickstart

        :param bool rootpw_seen: if rootpw should be considered as coming from kickstart
        """
        self.implementation.set_rootpw_seen(rootpw_seen)

    @property
    def RootPassword(self) -> Str:
        """Root password.

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can configure the root password

        :return: root password (might be crypted)
        """
        return self.implementation.root_password

    @property
    def IsRootPasswordCrypted(self) -> Bool:
        """Is the root password crypted ?

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can configure the root password

        :return: True, if the root password is crypted, otherwise False
        """
        return self.implementation.root_password_is_crypted

    @emits_properties_changed
    def SetCryptedRootPassword(self, crypted_root_password: Str):
        """Set the root password.

        The password is expected to be provided in already crypted.

        :param crypted_root_password: already crypted root password
        """
        self.implementation.set_root_password(crypted_root_password, crypted=True)

    @emits_properties_changed
    def ClearRootPassword(self):
        """Clear any set root password."""
        self.implementation.clear_root_password()

    @property
    def IsRootPasswordSet(self) -> Bool:
        """Is the root password set ?

        :return: True, if the root password is set, otherwise False
        """
        return self.implementation.root_password_is_set

    @emits_properties_changed
    def SetRootAccountLocked(self, root_account_locked: Bool):
        """Lock or unlock the root account."""
        self.implementation.set_root_account_locked(root_account_locked)

    @property
    def IsRootAccountLocked(self) -> Bool:
        """Is the root account locked ?

        :return: True, if the root account is locked, otherwise False
        """
        return self.implementation.root_account_locked
