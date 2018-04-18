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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

from pyanaconda import input_checking
from pyanaconda.pwpolicy import F22_PwPolicyData
from pyanaconda.core import constants
from pyanaconda.core.i18n import _
import unittest

def get_policy():
    return F22_PwPolicyData()

class PasswordQuality(unittest.TestCase):
    def password_empty_test(self):
        """Check if quality of an empty password is reported correctly."""
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)  # empty password is fine with emptyok policy
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)
        # empty password should override password-too-short messages
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.minlen = 10
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)

    def password_empty_ok_test(self):
        """Check if the empty_ok flag works correctly."""
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.emptyok = True
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)
        # empty_ok with password length
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.emptyok = True
        request.policy.minlen = 10
        request.password = ""
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)
        # non-empty passwords that are too short should still get a score of 0 & the "too short" message
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.emptyok = True
        request.policy.minlen = 10
        request.password = "123"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 0)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)
        # also check a long-enough password, just in case
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.emptyok = True
        request.policy.minlen = 10
        request.password = "1234567891"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.WEAK.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)

    def password_length_test(self):
        """Check if minimal password length is checked properly."""
        # first check if the default minimal password length is checked correctly
        # (should be 6 characters at the moment)
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "123"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 0)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))

        # weak but long enough
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "123456"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 1)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.WEAK.value))

        # check if setting password length works correctly
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.minlen = 10
        request.password = "12345"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 0)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.minlen = 10
        request.password = "1234567891"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertGreater(check.result.password_score, 0)
        self.assertNotEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))

    def password_quality_test(self):
        """Check if libpwquality gives reasonable numbers & score is assigned correctly."""
        # " " should give score 0 (<6 chars) & quality 0
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = " "
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertEqual(check.result.password_score, 0)
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)

        # "anaconda" is a dictionary word
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "anaconda"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertGreater(check.result.password_score, 0)
        self.assertNotEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertNotEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)

        # "jelenovipivonelej" is a palindrome
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "jelenovipivonelej"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertGreater(check.result.password_score, 0)
        self.assertNotEqual(check.result.status_text, _(constants.SecretStatus.EMPTY.value))
        self.assertNotEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        self.assertEqual(check.result.password_quality, 0)
        self.assertIsNotNone(check.result.error_message)

        # "4naconda-" gives a quality of 27 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "4naconda-"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertIs(check.result.error_message, "")

        # "4naconda----" gives a quality of 52 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "4naconda----"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertIs(check.result.error_message, "")

        # "----4naconda----" gives a quality of 80 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "----4naconda----"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        self.assertIs(check.result.error_message, "")

        # "?----4naconda----?" gives a quality of 100 on RHEL7
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.password = "?----4naconda----?"
        check = input_checking.PasswordValidityCheck()
        check.run(request)

        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(check.result.password_score, 4)  # quality > 90
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.STRONG.value))
        self.assertEqual(check.result.password_quality, 100)
        self.assertIs(check.result.error_message, "")

        # a long enough strong password with minlen set
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.minlen = 10
        request.password = "!?----4naconda----?!"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(check.result.password_score, 4)  # quality > 90
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.STRONG.value))
        self.assertEqual(check.result.password_quality, 100)
        self.assertIs(check.result.error_message, "")

        # minimum password length overrides strong passwords for score and status
        request = input_checking.PasswordCheckRequest()
        request.policy = get_policy()
        request.policy.minlen = 30
        request.password = "?----4naconda----?"
        check = input_checking.PasswordValidityCheck()
        check.run(request)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(check.result.password_score, 0)  # too short
        self.assertEqual(check.result.status_text, _(constants.SecretStatus.TOO_SHORT.value))
        self.assertEqual(check.result.password_quality, 0)  # dependent on password length
        self.assertIs(check.result.error_message,
                      _(constants.SECRET_TOO_SHORT[constants.SecretType.PASSWORD]))
