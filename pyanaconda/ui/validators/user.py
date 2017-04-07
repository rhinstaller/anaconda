# The class user validation.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import logging

from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _
from pyanaconda.ui.common import check_environment_firstboot
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.hardware import HardwareValidator

log = logging.getLogger("anaconda")

__all__ = ["UserValidator"]


def user_exist(data):
    """Is the user account created?"""
    return len(data.user.userList) > 0


class UserValidator(BaseValidator):
    """A class to check the user account."""

    title = N_("User validation")
    depends_on = [HardwareValidator]

    @classmethod
    def should_create(cls, config):
        return check_environment_firstboot(
            data=config.data,
            firstboot_data_check=(not user_exist(config.data)))

    def __init__(self, config):
        super(UserValidator, self).__init__(config)
        self._data = config.data

        # Get the user data.
        if self._data.user.userList:
            self._user = self._data.user.userList[0]
            self._user._create = True
        else:
            self._user = self._data.UserData()
            self._user._create = False

        # Should we use the password?
        self._user._use_password = self._user.isCrypted or self._user.password

        # Configure the password policy, if available.
        self._policy = self._data.anaconda.pwpolicy.get_policy("user")

        #  Otherwise use defaults.
        if not self._policy:
            self._policy = self._data.anaconda.PwPolicyData()

    def should_validate(self):
        # Do not continue if the data were kickstarted and it is not
        # allowed to change them and they are complete.
        return not (self._is_valid() and flags.automatedInstall
                    and self._data.user.seen and not self._policy.changesok)

    def _is_mandatory(self):
        """Is the validation mandatory?"""
        # Mandatory if the root password hasn't been set and
        # the root account was not locked in a kickstart.
        return not self._data.rootpw.password and not self._data.rootpw.lock

    def _is_valid(self):
        """Verify that a user was created and a password is set."""
        return user_exist(self._data) and self._is_password_set()

    def _is_password_set(self):
        """Is the user password set?"""
        return not self._user._use_password or self._user.password or self._user.isCrypted

    def _get_validation_error(self):
        """Return the validation error message."""
        if not user_exist(self._data):
            return _("User is not created.")

        elif not self._is_password_set():
            return _("The user password is not set.")

        else:
            return _("The user validation has failed.")
