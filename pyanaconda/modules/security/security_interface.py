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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import SECURITY
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.realm import RealmData
from pyanaconda.modules.security.constants import SELinuxMode


@dbus_interface(SECURITY.interface_name)
class SecurityInterface(KickstartModuleInterface):
    """DBus interface for the security module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("SELinux", self.implementation.selinux_changed)
        self.watch_property("Authselect", self.implementation.authselect_changed)
        self.watch_property(
            "FingerprintAuthEnabled", self.implementation.fingerprint_auth_enabled_changed
        )
        self.watch_property("Realm", self.implementation.realm_changed)

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
        return self.implementation.selinux.value

    @SELinux.setter
    @emits_properties_changed
    def SELinux(self, value: Int):
        """Sets the state of SELinux on the installed system.

        SELinux defaults to enforcing in anaconda.

        :param value: a value of the SELinux state
        """
        self.implementation.set_selinux(SELinuxMode(value))

    @property
    def Authselect(self) -> List[Str]:
        """Arguments for the authselect tool.

        :return: a list of arguments
        """
        return self.implementation.authselect

    @Authselect.setter
    @emits_properties_changed
    def Authselect(self, args: List[Str]):
        """Set the arguments for the authselect tool.

        Example: ['select', 'sssd']

        :param args: a list of arguments
        """
        self.implementation.set_authselect(args)

    @property
    def Realm(self) -> Structure:
        """Specification of the enrollment in a realm.

        :return: a dictionary with a specification
        """
        return RealmData.to_structure(self.implementation.realm)

    @Realm.setter
    @emits_properties_changed
    def Realm(self, realm: Structure):
        """Specify of the enrollment in a realm.

        The DBus structure is defined by RealmData.

        :param realm: a dictionary with a specification
        """
        self.implementation.set_realm(RealmData.from_structure(realm))

    @property
    def FingerprintAuthEnabled(self) -> Bool:
        """Reports if fingerprint authentication is enabled.

        :return: True if fingerprint authentication is enabled, False otherwise
        """
        return self.implementation.fingerprint_auth_enabled

    @FingerprintAuthEnabled.setter
    @emits_properties_changed
    def FingerprintAuthEnabled(self, fingerprint_auth_enabled: bool):
        """Set if fingerprint authentication should be enabled.

        :param bool fingerprint_auth_enabled: set to True to enable fingerprint authentication,
                                              False otherwise
        """
        self.implementation.set_fingerprint_auth_enabled(fingerprint_auth_enabled)

    def DiscoverRealmWithTask(self) -> ObjPath:
        """Discover realm with a task.

        NOTE: temporary API needed before dynamic task scheduling is implemented
        """
        return TaskContainer.to_object_path(
            self.implementation.discover_realm_with_task()
        )

    def JoinRealmWithTask(self) -> ObjPath:
        """Join realm with a task.

        NOTE: temporary API needed before dynamic task scheduling is implemented
        """
        return TaskContainer.to_object_path(
            self.implementation.join_realm_with_task()
        )

    def PreconfigureFIPSWithTask(self, payload_type: Str) -> ObjPath:
        """Set up FIPS for the payload installation with a task.

        :param payload_type: a string with the payload type
        :return: a DBus path of a installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.preconfigure_fips_with_task(payload_type)
        )

    def ConfigureFIPSWithTask(self) -> ObjPath:
        """Configure FIPS on the installed system.

        :return: a DBus path of a installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_fips_with_task()
        )
