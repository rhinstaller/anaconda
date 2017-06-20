#
# password_checking.py : policy based password checking
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from pyanaconda.isignal import Signal

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PasswordCheck(object):
    """Handle a password validation check."""

    def __init__(self, checker):
        self._checker = checker

    def check_password_and_confirmarion(self):
        raise NotImplementedError

    def check_confirmation(self):
        raise NotImplementedError





    def check_password_empty(self, inputcheck):
        """Check whether a password has been specified at all.

           This check is used for both the password and the confirmation.
        """
        # If the password was set by kickstart, skip the check.
        # pylint: disable=no-member
        if self.input_kickstarted and not self.policy.changesok:
            return InputCheck.CHECK_OK

        # Skip the check if no password is required
        if (not self.input_enabled) or self.input_kickstarted:
            return InputCheck.CHECK_OK
        # Also skip the check if the policy says that an empty password is fine
        # and non-empty password is not required by the screen.
        # pylint: disable=no-member
        elif self.policy.emptyok and not self.password_required:
            return InputCheck.CHECK_OK
        elif not self.get_input(inputcheck.input_obj):
            # pylint: disable=no-member
            if self.policy.strict or self.password_required:
                return _(constants.PASSWORD_EMPTY_ERROR) % {"password": self.name_of_input}
            else:
                if self.waive_clicks > 1:
                    return InputCheck.CHECK_OK
                else:
                    return _(constants.PASSWORD_EMPTY_ERROR) % {"password": self.name_of_input} + " " + _(constants.PASSWORD_DONE_TWICE)
        else:
            return InputCheck.CHECK_OK



class PasswordChecker(object):

    def __init__(self, policy):
        self._policy = policy
        self._checks = []
        self.password_changed = Signal()
        self.password_confirmation_changed = Signal()
        self.password_waived = Signal()
        self._waive_count = 0

    def add_check(self, check):
        self._check.append(check)









