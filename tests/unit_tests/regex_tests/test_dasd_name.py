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

from pyanaconda.core.regexes import DASD_DEVICE_NUMBER


class DASDNameRegexTestCase(unittest.TestCase):

    def test_device_name(self):
        good_tests = [
                '0.0.0000',
                '0.0.abcd',
                '0.0.ABCD',
                '1.2.3456',
                '1.2.000a',
                '1.2.00a',
                '1.2.0a',
                '1.2.a',
                '.000a',
                '.00a',
                '.0a',
                '.a',
                '000a',
                '00a',
                '0a',
                'a',
                ]

        bad_tests = [
                'totalnonsens',
                'a.a.0000',
                '0.0.gggg',
                '0.000a',
                '0.0.',
                '01.01.abcd',
                '0.0.abcde',
                '',
                ]

        assert regex_match(DASD_DEVICE_NUMBER, good_tests, bad_tests)
