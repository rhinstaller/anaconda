#!/usr/bin/python
# vim:set fileencoding=utf-8
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

import unittest

from regexcheck import regex_match

from pyanaconda.core.regexes import NM_MAC_INITRAMFS_CONNECTION


class NMMacInitramfsConnectionTestCase(unittest.TestCase):
    def test_initramfs_connection(self):
        good_tests = [
            '12:24:56:78:ab:cd',
            '12:24:56:78:AB:cd',
            '12:24:56:78:AB:CD',
        ]

        bad_tests = [
            '',
            '12:24:56:789:ab:cd',
            '12:24:56:78:AB:cg',
            '12:24:56:78:ab:cd:ef',
            '12-24-56-78-ab-cd',
            '12-24-56-78-AB-CD',
            '12:24:56:78-ab-cd',
            '12:24:56:78-AB-CD',
            '12:24:56:78:ab',
            # Infiniband MAC address
            '80:00:02:00:fe:80:00:00:00:00:00:00:f4:52:14:03:00:7b:cb:a3',
        ]

        assert regex_match(NM_MAC_INITRAMFS_CONNECTION, good_tests, bad_tests)
