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
from pyanaconda.core.regexes import ISCSI_IQN_NAME_REGEX, ISCSI_EUI_NAME_REGEX

class iSCSIiqnnameRegexTestCase(unittest.TestCase):
    def iqnname_test(self):
        good_tests = [
                'iqn.2014-15.com.example',
                'iqn.2014-15.com.example:iscsi',
                'iqn.2014-15.c-om.example:iscsi',
                'iqn.2014-15.c.om.example:iscsi',
                'iqn.2014-15.com.example:...',
                'iqn.2014-15.com.example:iscsi_@nything_except_colon_after_colon!'
                ]

        bad_tests = [
                'iqn',
                'iqn.',
                'iqn.2014-15',
                'iqn.2014-15.',
                'iqn.2014-15..',
                'iqn.2014-15.com.example.',
                'iqn.2014-15.com.example...',
                'iqn.2014-15.com.example:',
                'iqn.2014-15.-com.example',
                'iqn.2014-15.com-.example',
                'iqn.2014-15.-.example',
                'iqn.2014-15.com.example-:iscsi',
                'abciqn.2014-15.com.example:iscsi',
                'iqn.2014-15.-.example:iscsi',
                'iqn.2014-15.com&com.example:iscsi',
                'iqn.2014-15.com.example:iscsi:doublecolon',
                'iqn.2014-15..om.example:iscsi',
                ]

        if not regex_match(ISCSI_IQN_NAME_REGEX, good_tests, bad_tests):
            self.fail()

class iSCSIeuinameRegexTestCase(unittest.TestCase):
    def euiname_test(self):
        good_tests = [
                'eui.ABCDEF0123456789',
                'eui.abcdef0123456789',
                'eui.0123456789ABCDEF'
                ]

        bad_tests = [
                'eui',
                'eui.',
                'eui.2014-',
                'eui.exampleeui789abc'
                'eui.AAAABBBBCCC2345',
                'eui.AAAABBBBCCCCD4567'
                ]

        if not regex_match(ISCSI_EUI_NAME_REGEX, good_tests, bad_tests):
            self.fail()
