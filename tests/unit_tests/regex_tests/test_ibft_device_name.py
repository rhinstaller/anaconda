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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest

from pyanaconda.core.regexes import IBFT_CONFIGURED_DEVICE_NAME

def _run_tests(testcase, expression, goodlist, badlist):
    got_error = False
    for good in goodlist:
        try:
            testcase.assertIsNotNone(expression.match(good))
        except AssertionError:
            got_error = True
            print("Good string %s did not match expression" % good)

    for bad in badlist:
        try:
            testcase.assertIsNone(expression.match(bad))
        except AssertionError:
            got_error = True
            print("Bad string %s matched expression" % bad)

    if got_error:
        testcase.fail()

class IbftDeviceNameTestCase(unittest.TestCase):
    def test_netmask(self):
        good_tests = [
                'ibft0',
                'ibft1',
                'ibft11',
                ]

        bad_tests = [
                'myibft0',
                'ibft',
                'ibftfirst',
                'ibgt0',
                ]

        _run_tests(self, IBFT_CONFIGURED_DEVICE_NAME, good_tests, bad_tests)
