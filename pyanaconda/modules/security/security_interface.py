#
# DBus interface for the security module.
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
from pyanaconda.core.constants import REALM_NAME, REALM_DISCOVER, REALM_JOIN
from pyanaconda.dbus.constants import MODULE_SECURITY_NAME
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(MODULE_SECURITY_NAME)
class SecurityInterface(KickstartModuleInterface):
    """DBus interface for the security module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.selinux_changed.connect(self.changed("SELinux"))
        self.implementation.authselect_changed.connect(self.changed("Authselect"))
        self.implementation.authconfig_changed.connect(self.changed("Authconfig"))
        self.implementation.realm_changed.connect(self.changed("Realm"))

    @property
    def SELinux(self) -> Int:
        """The state of SELinux on the installed system.

        Allowed values:
          -1  Unset.
           0  Disabled.
           1  Enforcing.
           2  Permissive.

        :return: a value of the SELinux state
        """
        return self.implementation.selinux

    @emits_properties_changed
    def SetSELinux(self, value: Int):
        """Sets the state of SELinux on the installed system.

        SELinux defaults to enforcing in anaconda.

        :param value: a value of the SELinux state
        """
        self.implementation.set_selinux(value)

    @property
    def Authselect(self) -> List[Str]:
        """Arguments for the authselect tool.

        :return: a list of arguments
        """
        return self.implementation.authselect

    @emits_properties_changed
    def SetAuthselect(self, args: List[Str]):
        """Set the arguments for the authselect tool.

        Example: ['select', 'sssd']

        :param args: a list of arguments
        """
        self.implementation.set_authselect(args)

    @property
    def Authconfig(self) -> List[Str]:
        """Arguments for the authconfig tool.

        Authconfig is deprecated, use authselect.

        :return: a list of arguments
        """
        return self.implementation.authconfig

    @emits_properties_changed
    def SetAuthconfig(self, args: List[Str]):
        """Set the arguments for the authconfig tool.

        Authconfig is deprecated, use authselect.

        Example: ['--passalgo=sha512', '--useshadow']

        :param args: a list of arguments
        """
        self.implementation.set_authconfig(args)

    @property
    def Realm(self) -> Dict[Str, Variant]:
        """Specification of the enrollment in a realm.

        :return: a dictionary with a specification
        """
        realm = self.implementation.realm

        return {
            REALM_NAME: get_variant(Str, realm.get(REALM_NAME, "")),
            REALM_DISCOVER: get_variant(List[Str], realm.get(REALM_DISCOVER, [])),
            REALM_JOIN: get_variant(List[Str], realm.get(REALM_JOIN, []))
        }

    @emits_properties_changed
    def SetRealm(self, realm: Dict[Str, Variant]):
        """Specify of the enrollment in a realm.

        Example:
        {
            'name': 'domain.example.com',
            'discover': ['--client-software=sssd'],
            'join': ['--no-password', '--client-software=sssd']
        }

        :param realm: a dictionary with a specification
        """
        self.implementation.set_realm(realm)
