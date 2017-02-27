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

# Ignore the potfiles check as it thinks we add translatable strings with _(),
# but we just use it to translate the content of variables.
#
# TODO: remove the ignore-check once the potfile check is fixed
#
# ignore-check: potfiles


from pyanaconda.users import validatePassword, PasswordCheckRequest
from pyanaconda import constants
from pyanaconda.i18n import _
import unittest
import platform

# libpwquality gives different results when running on RHEL and elsewhere,
# so we need to skip absolute quality value checking outside of RHEL
ON_RHEL = platform.dist()[0] == "redhat"

class PasswordQuality(unittest.TestCase):
    def password_empty_test(self):
        """Check if quality of an empty password is reported correctly."""
        request = PasswordCheckRequest("")
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)
        # empty password should override password-too-short messages
        request = PasswordCheckRequest("", minimum_length=10)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)

    def password_empty_ok_test(self):
        """Check if the empty_ok flag works correctly."""
        request = PasswordCheckRequest("", empty_ok=True)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 1)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)
        # empty_ok should override password length
        request = PasswordCheckRequest("", minimum_length=10, empty_ok=True)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 1)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)
        # non-empty passwords that are too short should still get a score of 0 & the "too short" message
        request = PasswordCheckRequest("123", minimum_length=10, empty_ok=True)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)
        # also check a long-enough password, just in case
        request = PasswordCheckRequest("1234567891", minimum_length=10, empty_ok=True)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 1)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_WEAK))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)

    def password_length_test(self):
        """Check if minimal password length is checked properly."""
        # first check if the default minimal password length is checked correctly
        # (should be 6 characters at the moment)
        request = PasswordCheckRequest("123")
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        request = PasswordCheckRequest("123456")
        result = validatePassword(request)
        self.assertGreater(result.password_score, 0)
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))

        # check if setting password length works correctly
        request = PasswordCheckRequest("12345", minimum_length=10)
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        request = PasswordCheckRequest("1234567891", minimum_length=10)
        result = validatePassword(request)
        self.assertGreater(result.password_score, 0)
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))

    def password_quality_test(self):
        """Check if libpwquality gives reasonable numbers & score is assigned correctly."""
        # " " should give score 0 (<6 chars) & quality 0
        request = PasswordCheckRequest(" ")
        result = validatePassword(request)
        self.assertEqual(result.password_score, 0)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)

        # "anaconda" is a dictionary word
        request = PasswordCheckRequest("anaconda")
        result = validatePassword(request)
        self.assertGreater(result.password_score, 0)
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)

        # "jelenovipivonelej" is a palindrome
        request = PasswordCheckRequest("jelenovipivonelej")
        result = validatePassword(request)
        self.assertGreater(result.password_score, 0)
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_EMPTY))
        self.assertNotEqual(result.status_text, _(constants.PASSWORD_STATUS_TOO_SHORT))
        self.assertEqual(result.password_quality, 0)
        self.assertIsNotNone(result.error_message)

        # "4naconda-" gives reasonable quality (76) on RHEL7
        request = PasswordCheckRequest("4naconda-")
        result = validatePassword(request)
        if ON_RHEL:
            self.assertEqual(result.password_score, 4)
            self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_STRONG))
            self.assertEqual(result.password_quality, 76)
        self.assertIsNone(result.error_message)

        # "?----4naconda----?" gives a quality of 100 on RHEL7
        request = PasswordCheckRequest("?----4naconda----?")
        result = validatePassword(request)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(result.password_score, 4)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_STRONG))
        self.assertEqual(result.password_quality, 100)
        self.assertIsNone(result.error_message)

        # a long enough strong password with minlen set
        request = PasswordCheckRequest("?----4naconda----??!!", minimum_length=10)
        result = validatePassword(request)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(result.password_score, 4)
        self.assertEqual(result.status_text, _(constants.PASSWORD_STATUS_STRONG))
        self.assertEqual(result.password_quality, 100)
        self.assertIsNone(result.error_message)
