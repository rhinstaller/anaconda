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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#

import unittest

from pyanaconda.core.users import check_grouplist, check_groupname, check_username


class UserNameTests(unittest.TestCase):

    def _check_name(self, name):
        return check_username(name)

    def _assert_name(self, name, expected_validity):
        valid, message = self._check_name(name)
        assert valid == expected_validity, message
        assert (not valid) == (message is not None)

    def test_reserved_names(self):
        """Test the reserved names."""
        self._assert_name("root", False)
        self._assert_name("home", False)
        self._assert_name("system", False)
        self._assert_name("mail", False)
        self._assert_name("nobody", False)
        self._assert_name("operator", False)
        self._assert_name("ftp", False)
        self._assert_name("adm", False)
        self._assert_name("bin", False)
        self._assert_name("lp", False)
        self._assert_name("sync", False)
        self._assert_name("shutdown", False)
        self._assert_name("halt", False)
        self._assert_name("games", False)

        self._assert_name("foo", True)

    def test_hyphen(self):
        """Test names with a hyphen."""
        self._assert_name("-foo", False)
        self._assert_name("-f", False)
        self._assert_name("-", False)

        self._assert_name("f-", True)
        self._assert_name("foo-", True)

    def test_dots(self):
        """Test dots."""
        self._assert_name(".", False)
        self._assert_name("..", False)

        self._assert_name("...", True)

    def test_numbers(self):
        """Test numbers in names."""
        self._assert_name("1", False)
        self._assert_name("12", False)
        self._assert_name("123", False)

        self._assert_name("1a", True)
        self._assert_name("12a", True)
        self._assert_name("123a", True)

    def test_dolar(self):
        """Test a dolar in names."""
        self._assert_name("$", False)
        self._assert_name("$f", False)
        self._assert_name("f$oo", False)

        self._assert_name("f$", True)
        self._assert_name("foo$", True)

    def test_chars(self):
        """Test invalid characters."""
        self._assert_name("?", False)
        self._assert_name("f?", False)
        self._assert_name("foo?", False)

        self._assert_name("fo.o", True)
        self._assert_name("fo_o", True)
        self._assert_name("fo-o", True)
        self._assert_name("fo9o", True)

    def test_length(self):
        """Test the length of names."""
        self._assert_name("f" * 33, False)

        self._assert_name("f" * 32, True)
        self._assert_name("f" * 1, True)


class GroupNameTests(UserNameTests):

    def _check_name(self, name):
        return check_groupname(name)

    def test_reserved_names(self):
        """There are no reserved names for groups."""
        self._assert_name("root", True)
        self._assert_name("home", True)
        self._assert_name("system", True)

    def test_numbers(self):
        """Test numbers in names."""
        super().test_numbers()
        self._assert_name("0", False)


class GroupListTests(GroupNameTests):

    def _check_name(self, name):
        return check_grouplist(name)

    def test_grouplist(self):
        """Test a simple list of groups."""
        self._assert_name("", True)
        self._assert_name("foo", True)
        self._assert_name(" foo", True)
        self._assert_name(" \tfoo", True)
        self._assert_name("foo ", True)
        self._assert_name("foo \t", True)
        self._assert_name("  foo  ", True)
        self._assert_name("foo,bar", True)
        self._assert_name("foo, bar", True)
        self._assert_name("  foo,    bar", True)
        self._assert_name("foo, bar, xxx", True)

        self._assert_name(",", False)
        self._assert_name("foo, -bar,", False)
        self._assert_name("foo,", False)
        self._assert_name("foo,   ", False)
        self._assert_name(",bar", False)
        self._assert_name("   ,bar", False)
        self._assert_name(",foo,", False)
        self._assert_name("foo,bar,", False)
