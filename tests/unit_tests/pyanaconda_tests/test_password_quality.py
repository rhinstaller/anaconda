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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import unittest

from pyanaconda import input_checking
from pyanaconda.core import constants
from pyanaconda.core.constants import PASSWORD_POLICY_USER
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.policy import PasswordPolicy


def get_policy():
    return PasswordPolicy.from_defaults(PASSWORD_POLICY_USER)


class PasswordQuality(unittest.TestCase):
    def test_password_empty(self):
        """Check if quality of an empty password is reported correctly."""
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1  # empty password is fine with emptyok policy
        assert check.result.status_text == _(constants.SecretStatus.EMPTY.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None
        # empty password should override password-too-short messages
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.min_length = 10
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1
        assert check.result.status_text == _(constants.SecretStatus.EMPTY.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None

    def test_password_empty_ok(self):
        """Check if the empty_ok flag works correctly."""
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.allow_empty = True
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1
        assert check.result.status_text == _(constants.SecretStatus.EMPTY.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None
        # empty_ok with password length
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.allow_empty = True
        request.policy.min_length = 10
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1
        assert check.result.status_text == _(constants.SecretStatus.EMPTY.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None
        # non-empty passwords that are too short should still get a score of 0 & the "too short" message
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.allow_empty = True
        request.policy.min_length = 10
        request.password = "123"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 0
        assert check.result.status_text == _(constants.SecretStatus.TOO_SHORT.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None
        # also check a long-enough password, just in case
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.allow_empty = True
        request.policy.min_length = 10
        request.password = "1234567891"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1
        assert check.result.status_text == _(constants.SecretStatus.WEAK.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None

    def test_password_length(self):
        """Check if minimal password length is checked properly."""
        # first check if the default minimal password length is checked correctly
        # (should be 6 characters at the moment)
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "123"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 0
        assert check.result.status_text == _(constants.SecretStatus.TOO_SHORT.value)

        # weak but long enough
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "123456"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 1
        assert check.result.status_text == _(constants.SecretStatus.WEAK.value)

        # check if setting password length works correctly
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.min_length = 10
        request.password = "12345"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 0
        assert check.result.status_text == _(constants.SecretStatus.TOO_SHORT.value)
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.min_length = 10
        request.password = "1234567891"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score > 0
        assert check.result.status_text != _(constants.SecretStatus.TOO_SHORT.value)

    def test_password_quality(self):
        """Check if libpwquality gives reasonable numbers & score is assigned correctly."""
        # " " should give score 0 (<6 chars) & quality 0
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = " "
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score == 0
        assert check.result.status_text == _(constants.SecretStatus.TOO_SHORT.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None

        # "anaconda" is a dictionary word
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "anaconda"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score > 0
        assert check.result.status_text != _(constants.SecretStatus.EMPTY.value)
        assert check.result.status_text != _(constants.SecretStatus.TOO_SHORT.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None

        # "jelenovipivonelej" is a palindrome
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "jelenovipivonelej"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.password_score > 0
        assert check.result.status_text != _(constants.SecretStatus.EMPTY.value)
        assert check.result.status_text != _(constants.SecretStatus.TOO_SHORT.value)
        assert check.result.password_quality == 0
        assert check.result.error_message is not None

        # "4naconda-" gives a quality of 27 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "4naconda-"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.error_message == ""

        # "4naconda----" gives a quality of 52 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "4naconda----"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.error_message == ""

        # "----4naconda----" gives a quality of 80 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "----4naconda----"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        assert check.result.error_message == ""

        # "?----4naconda----?" gives a quality of 100 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "?----4naconda----?"
        check = input_checking.PasswordValidityCheck()
        check.run(request)

        # this should (hopefully) give quality 100 everywhere
        assert check.result.password_score == 4  # quality > 90
        assert check.result.status_text == _(constants.SecretStatus.STRONG.value)
        assert check.result.password_quality == 100
        assert check.result.error_message == ""

        # a long enough strong password with minlen set
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.min_length = 10
        request.password = "!?----4naconda----?!"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        # this should (hopefully) give quality 100 everywhere
        assert check.result.password_score == 4  # quality > 90
        assert check.result.status_text == _(constants.SecretStatus.STRONG.value)
        assert check.result.password_quality == 100
        assert check.result.error_message == ""

        # minimum password length overrides strong passwords for score and status
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.min_length = 30
        request.password = "?----4naconda----?"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        # this should (hopefully) give quality 100 everywhere
        assert check.result.password_score == 0  # too short
        assert check.result.status_text == _(constants.SecretStatus.TOO_SHORT.value)
        assert check.result.password_quality == 0  # dependent on password length
        assert check.result.error_message == \
            _(constants.SECRET_TOO_SHORT[constants.SecretType.PASSWORD])
