# -*- coding: utf-8 -*-
#
# Copyright (C) 2017  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#

import unittest
from pyanaconda.users import check_username


class UserNameTests(unittest.TestCase):

    def _assert_username(self, name, expected_validity):
        valid, message = check_username(name)
        self.assertEqual(valid, expected_validity, message)
        self.assertEqual(not valid, message is not None)

    def reserved_names_test(self):
        """Test the reserved names."""
        self._assert_username("root", False)
        self._assert_username("home", False)
        self._assert_username("system", False)

        self._assert_username("foo", True)

    def hyphen_test(self):
        """Test names with a hyphen."""
        self._assert_username("-foo", False)
        self._assert_username("-f", False)
        self._assert_username("-", False)

        self._assert_username("f-", True)
        self._assert_username("foo-", True)

    def dots_test(self):
        """Test dots."""
        self._assert_username(".", False)
        self._assert_username("..", False)

        self._assert_username("...", True)

    def numbers_test(self):
        """Test numbers in names."""
        self._assert_username("1", False)
        self._assert_username("12", False)
        self._assert_username("123", False)

        self._assert_username("1a", True)
        self._assert_username("12a", True)
        self._assert_username("123a", True)

    def dolar_test(self):
        """Test a dolar in names."""
        self._assert_username("$", False)
        self._assert_username("$f", False)
        self._assert_username("f$oo", False)

        self._assert_username("f$", True)
        self._assert_username("foo$", True)

    def chars_test(self):
        """Test invalid characters."""
        self._assert_username("?", False)
        self._assert_username("f?", False)
        self._assert_username("foo?", False)

        self._assert_username("fo.o", True)
        self._assert_username("fo_o", True)
        self._assert_username("fo-o", True)
        self._assert_username("fo9o", True)

    def length_test(self):
        """Test the length of names."""
        self._assert_username("f" * 33, False)

        self._assert_username("f" * 32, True)
        self._assert_username("f" * 1, True)
