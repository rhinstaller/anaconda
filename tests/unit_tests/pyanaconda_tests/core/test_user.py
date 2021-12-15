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

import os
import tempfile
import unittest
from unittest.mock import patch
from pyanaconda.core.path import make_directories
from pyanaconda.core.users import check_username, check_groupname, check_grouplist, \
    _dir_tree_map, _chown_dir_tree


class UserNameTests(unittest.TestCase):

    def _check_name(self, name):
        return check_username(name)

    def _assert_name(self, name, expected_validity):
        valid, message = self._check_name(name)
        assert valid == expected_validity, message
        assert (not valid) == (message is not None)

    def _assert_username(self, name, expected_validity):
        self._assert_name(name, expected_validity)

    def test_reserved_names(self):
        """Test the reserved names."""
        self._assert_username("root", False)
        self._assert_username("home", False)
        self._assert_username("system", False)

        self._assert_username("foo", True)

    def test_hyphen(self):
        """Test names with a hyphen."""
        self._assert_username("-foo", False)
        self._assert_username("-f", False)
        self._assert_username("-", False)

        self._assert_username("f-", True)
        self._assert_username("foo-", True)

    def test_dots(self):
        """Test dots."""
        self._assert_username(".", False)
        self._assert_username("..", False)

        self._assert_username("...", True)

    def test_numbers(self):
        """Test numbers in names."""
        self._assert_username("1", False)
        self._assert_username("12", False)
        self._assert_username("123", False)

        self._assert_username("1a", True)
        self._assert_username("12a", True)
        self._assert_username("123a", True)

    def test_dolar(self):
        """Test a dolar in names."""
        self._assert_username("$", False)
        self._assert_username("$f", False)
        self._assert_username("f$oo", False)

        self._assert_username("f$", True)
        self._assert_username("foo$", True)

    def test_chars(self):
        """Test invalid characters."""
        self._assert_username("?", False)
        self._assert_username("f?", False)
        self._assert_username("foo?", False)

        self._assert_username("fo.o", True)
        self._assert_username("fo_o", True)
        self._assert_username("fo-o", True)
        self._assert_username("fo9o", True)

    def test_length(self):
        """Test the length of names."""
        self._assert_username("f" * 33, False)

        self._assert_username("f" * 32, True)
        self._assert_username("f" * 1, True)


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


class ChownInternalsTest(unittest.TestCase):

    def test_dir_tree_map(self):
        """Test _dir_tree_map"""
        in_dirs = [
            "bla",
            "bla/bla",
            "have a space",
            "žluťoučký_kůň",
        ]
        in_files = [
            "foo",
            "bar",
            "baz",
            "bla/helloworld.txt",
            "have a space/for a file",
            "žluťoučký_kůň/123",
        ]
        found = []
        dirs = []
        files = []

        def _report(path):
            found.append(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            dirs.append(tmpdir)
            for d in in_dirs:
                path = os.path.join(tmpdir, d)
                make_directories(path)
                dirs.append(path)
            for f in in_files:
                path = os.path.join(tmpdir, f)
                os.mknod(path)
                files.append(path)

            # files
            found.clear()
            _dir_tree_map(tmpdir, _report, files=True, dirs=False)
            assert sorted(found) == sorted(files)

            # dirs
            found.clear()
            _dir_tree_map(tmpdir, _report, files=False, dirs=True)
            assert sorted(found) == sorted(dirs)

            # both
            found.clear()
            _dir_tree_map(tmpdir, _report, files=True, dirs=True)
            assert sorted(found) == sorted(dirs + files)

            # neither
            found.clear()
            _dir_tree_map(tmpdir, _report, files=False, dirs=False)
            assert not found

    @patch("pyanaconda.core.users._dir_tree_map")
    def test_chown_dir_tree(self, dtm_mock):
        """Test _chown_dir_tree

        It isn't possible to mock internal functions or lambdas, so having it pass is the best
        that can be done, barring some complicated setup in TemporaryDirectory.
        """
        _chown_dir_tree("somewhere", 123, 456)
        dtm_mock.assert_called_once()

        dtm_mock.reset_mock()
        _chown_dir_tree("somewhere", 0o0, 123, 456, 789)
