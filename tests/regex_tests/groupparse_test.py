#!/usr/bin/python
#
# Copyright (C) 2010-2013  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>
#
import unittest

from pyanaconda.regexes import GROUPLIST_FANCY_PARSE

class GroupParseTestCase(unittest.TestCase):
    def group_list_test(self):
        """Test a list of possible group-name (GID) values with the group
           parsing regex. 
           
           Tests are in the form of: (string, match.groups() tuple)
        """


        tests = [("group", ("group", None)),
                 ("group  ", ("group", None)),
                 ("  group", ("group", None)),
                 ("  group  ", ("group", None)),
                 ("group (1000)", ("group", "1000")),
                 ("group (1000)  ", ("group", "1000")),
                 ("  group (1000)", ("group", "1000")),
                 ("  group (1000)  ", ("group", "1000")),
                 ("group(1000)", ("group", "1000")),
                 ("(1000)", ("", "1000")),
                 ("  (1000)", ("", "1000")),
                 ("(1000)  ", ("", "1000")),
                 ("  (1000)  ", ("", "1000")),
                 ("group (1000", ("group (1000", None)),
                 ("group (abcd)", ("group (abcd)", None)),
                 ("", ("", None)),
                 ]

        got_error = False
        for group, result in tests:
            try:
                self.assertEqual(GROUPLIST_FANCY_PARSE.match(group).groups(), result)
            except AssertionError:
                got_error = True
                print("Group parse error: `%s' did not not parse as `%s'" % (group, result))

        if got_error:
            self.fail()
