#
# The user interface module
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PASSWORD_POLICY_LUKS, PASSWORD_POLICY_ROOT, \
    PASSWORD_POLICY_USER
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.boss.user_interface.ui_interface import UIInterface
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy

log = get_module_logger(__name__)

__all__ = ["UIModule"]


class UIModule(KickstartBaseModule):
    """The user interface module."""

    def __init__(self):
        super().__init__()
        self._password_policies = self.get_default_password_policies()
        self.password_policies_changed = Signal()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(USER_INTERFACE.object_path, UIInterface(self))

    @property
    def password_policies(self):
        """The password policies."""
        return self._password_policies

    def set_password_policies(self, policies):
        """Set the password policies.

        Default policy names:

            root  The policy for the root password.
            user  The policy for the user password.
            luks  The policy for the LUKS passphrase.

        :param policies: a dictionary of policy names and policy data
        """
        self._password_policies = policies
        self.password_policies_changed.emit()
        log.debug("Password policies are set to '%s'.", policies)

    def get_default_password_policies(self):
        """Get the default password policies.

        :return: a dictionary of policy names and policy data
        """
        return {
            PASSWORD_POLICY_ROOT: PasswordPolicy.from_defaults(PASSWORD_POLICY_ROOT),
            PASSWORD_POLICY_USER: PasswordPolicy.from_defaults(PASSWORD_POLICY_USER),
            PASSWORD_POLICY_LUKS: PasswordPolicy.from_defaults(PASSWORD_POLICY_LUKS),
        }
