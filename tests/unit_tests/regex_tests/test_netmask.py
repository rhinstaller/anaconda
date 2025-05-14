#!/usr/bin/python
# vim:set fileencoding=utf-8
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
import re
import unittest

from pyanaconda.core.regexes import IPV4_NETMASK_WITHOUT_ANCHORS


def _run_tests(testcase, expression, goodlist, badlist):
    errors = []
    for good in goodlist:
        try:
            testcase.assertIsNotNone(expression.match(good))
        except AssertionError:
            errors.append("Good string %s did not match expression" % good)

    for bad in badlist:
        try:
            testcase.assertIsNone(expression.match(bad))
        except AssertionError:
            errors.append("Bad string %s matched expression" % bad)

    testcase.assertEqual(errors, [])

class IPv4NetmaskTestCase(unittest.TestCase):
    def test_netmask(self):
        good_tests = [
                '255.255.255.0',
                '255.255.0.0',
                '255.255.255.254',
                '128.0.0.0',
                ]

        bad_tests = [
                '255.254.255.0',
                '24',
                '255',
                '255.0',
                '255.255.0',
                '192.168.1.1',
                '256.0.0.0'
                '255.b.255.0',
                '...',
                '255...'
                ]

        netmask_re = re.compile('^(' + IPV4_NETMASK_WITHOUT_ANCHORS + ')$')
        _run_tests(self, netmask_re, good_tests, bad_tests)
