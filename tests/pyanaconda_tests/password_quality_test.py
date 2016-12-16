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

from pyanaconda.users import validatePassword
from pyanaconda import constants
from pyanaconda.i18n import _
import unittest
import platform

# libpwquality gives different results when running on RHEL and elsewhere,
# so we need to skip absolute quality value checking outside of RHEL
#
# Ignore the deprecated method warning - we can revisist this when there is actually
# a replacement for platform.dist available for Fedora as a package.
# pylint: disable=deprecated-method
ON_RHEL = platform.dist()[0] == "redhat"

class PasswordQuality(unittest.TestCase):
    def password_empty_test(self):
        """Check if quality of an empty password is reported correctly."""
        score, status, quality, error_message = validatePassword("")
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)
        # empty password should override password-too-short messages
        score, status, quality, error_message = validatePassword("", minlen=10)
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)

    def password_empty_ok_test(self):
        """Check if the empty_ok flag works correctly."""
        score, status, quality, error_message = validatePassword("", empty_ok=True)
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)
        # empty_ok with password length
        score, status, quality, error_message = validatePassword("", minlen=10, empty_ok=True)
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)
        # non-empty passwords that are too short should still get a score of 0 & the "too short" message
        score, status, quality, error_message = validatePassword("123", minlen=10, empty_ok=True)
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)
        # also check a long-enough password, just in case
        score, status, quality, error_message = validatePassword("1234567891", minlen=10, empty_ok=True)
        self.assertEqual(score, 1)
        self.assertEqual(status, _(constants.PasswordStatus.WEAK.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)

    def password_length_test(self):
        """Check if minimal password length is checked properly."""
        # first check if the default minimal password length is checked correctly
        # (should be 6 characters at the moment)
        score, status, _quality, _error_message = validatePassword("123")
        self.assertEqual(score, 0)
        self.assertEqual(_(status), _(constants.PasswordStatus.TOO_SHORT.value))
        score, status, _quality, _error_message = validatePassword("123456")
        self.assertEqual(score, 1)
        self.assertEqual(_(status), _(constants.PasswordStatus.WEAK.value))

        # check if setting password length works correctly
        score, status, _quality, _error_message = validatePassword("12345", minlen=10)
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        score, status, _quality, _error_message = validatePassword("1234567891", minlen=10)
        self.assertGreater(score, 0)
        self.assertNotEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))

    def password_quality_test(self):
        """Check if libpwquality gives reasonable numbers & score is assigned correctly."""
        # " " should give score 0 (<6 chars) & quality 0
        score, status, quality, error_message = validatePassword(" ")
        self.assertEqual(score, 0)
        self.assertEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)

        # "anaconda" is a dictionary word
        score, status, quality, error_message = validatePassword("anaconda")
        self.assertGreater(score, 0)
        self.assertNotEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertNotEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)

        # "jelenovipivonelej" is a palindrome
        score, status, quality, error_message = validatePassword("jelenovipivonelej")
        self.assertGreater(score, 0)
        self.assertNotEqual(status, _(constants.PasswordStatus.EMPTY.value))
        self.assertNotEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        self.assertEqual(quality, 0)
        self.assertIsNotNone(error_message)

        # "4naconda-" gives a quality of 27 on RHEL7
        score, status, quality, error_message = validatePassword("4naconda-")
        if ON_RHEL:
            self.assertEqual(score, 1)  # quality < 50
            self.assertEqual(status, _(constants.PasswordStatus.WEAK.value))
            self.assertEqual(quality, 27)
        self.assertIsNone(error_message)

        # "4naconda----" gives a quality of 52 on RHEL7
        score, status, quality, error_message = validatePassword("4naconda----")
        if ON_RHEL:
            self.assertEqual(score, 2)  # quality > 50 & < 75
            self.assertEqual(status, _(constants.PasswordStatus.FAIR.value))
            self.assertEqual(quality, 52)
        self.assertIsNone(error_message)

        # "----4naconda----" gives a quality of 80 on RHEL7
        score, status, quality, error_message = validatePassword("----4naconda----")
        if ON_RHEL:
            self.assertEqual(score, 3)  # quality > 75 & < 90
            self.assertEqual(status, _(constants.PasswordStatus.GOOD.value))
            self.assertEqual(quality, 80)
        self.assertIsNone(error_message)

        # "?----4naconda----?" gives a quality of 100 on RHEL7
        score, status, quality, error_message = validatePassword("?----4naconda----?")
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(score, 4)  # quality > 90
        self.assertEqual(status, _(constants.PasswordStatus.STRONG.value))
        self.assertEqual(quality, 100)
        self.assertIsNone(error_message)

        # a long enough strong password with minlen set
        score, status, quality, error_message = validatePassword("?----4naconda----?", minlen=10)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(score, 4)  # quality > 90
        self.assertEqual(status, _(constants.PasswordStatus.STRONG.value))
        self.assertEqual(quality, 100)
        self.assertIsNone(error_message)

        # minimum password length overrides strong passwords for score and status
        score, status, quality, error_message = validatePassword("?----4naconda----?", minlen=30)
        # this should (hopefully) give quality 100 everywhere
        self.assertEqual(score, 0)  # too short
        self.assertEqual(status, _(constants.PasswordStatus.TOO_SHORT.value))
        self.assertEqual(quality, 100)  # independent on password length
        self.assertIsNone(error_message)
