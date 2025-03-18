#!/usr/bin/python
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest

from regexcheck import regex_match
from pyanaconda.core.regexes import ZFCP_LUN_NUMBER, ZFCP_WWPN_NUMBER


class ZFCPNameRegexTestCase(unittest.TestCase):

    def test_lun_name(self):
        good_tests = [
                '0x0000000000000000',
                '0x0123456789abcdef',
                '0x0123456789ABCDEF',
                '0x01234567',
                '0x0123',
                '0x0',
                '0000000000000000',
                '0123456789abcdef',
                '0123456789ABCDEF',
                '01234567',
                '0123',
                '0',
                ]

        bad_tests = [
                'totalnonsens',
                '0x00000000000000000',
                '0xabcdefg',
                '1x0',
                '0y0',
                '',
                ]

        assert regex_match(ZFCP_LUN_NUMBER, good_tests, bad_tests)

    def test_wwpn_name(self):
        good_tests = [
            '0x0000000000000000',
            '0x0123456789abcdef',
            '0x0123456789ABCDEF',
            '0000000000000000',
            '0123456789abcdef',
            '0123456789ABCDEF',
        ]

        bad_tests = [
            'totalnonsens',
            '0x00000000000000000',
            '0x000000000000000g',
            '0y0000000000000000',
            '0x000000000000000',
            '00000000000000000',
            '000000000000000g',
            '000000000000000',
            '0x0123456789abcde',
            '0x0123456789ABCDE',
            '0123456789abcde',
            '0123456789ABCDE',
            '0',
            '',
        ]

        assert regex_match(ZFCP_WWPN_NUMBER, good_tests, bad_tests)
