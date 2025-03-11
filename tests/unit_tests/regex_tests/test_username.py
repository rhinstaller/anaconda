#!/usr/bin/python3
# vim:set fileencoding=utf-8
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from regexcheck import regex_match

from pyanaconda.core.regexes import GECOS_VALID, GROUPLIST_SIMPLE_VALID, NAME_VALID


class UsernameRegexTestCase(unittest.TestCase):
    def test_gecos(self):
        """Test a list of possible Full Name values."""
        # These are valid full names
        good_tests = [
                '',
                'George',
                'George Burdell',
                'George P. Burdell',
                'Ğeorgé P. Burdełl',
                'Burdell, George',
                'g/p/b'
                ]

        # These are invalid full names
        bad_tests = ['George:Burdell']

        assert regex_match(GECOS_VALID, good_tests, bad_tests)

    def test_username(self):
        """Test a list of possible username values."""
        good_tests = [
                'gburdell',
                'GBurdell',
                'gburdell$',
                'g_burdell',
                '_burdell',
                'gggggggggggggggggggggggggburdell', # 32 characters
                'ggggggggggggggggggggggggburdell$',
                '_',
                'r',
                'ro',
                'roo',
                'roota',
                ]

        bad_tests = [
                '',
                '-gburdell',    # can't start with a hyphen
                'gburdełl',     # invalid character
                'g:burdell',
                'g burdell',
                'g,burdell',
                'ggggggggggggggggggggggggggburdell', # 33 characters
                'gggggggggggggggggggggggggburdell$',
                ' gburdell',
                ':gburdell',
                '$',
                '-'
                ]

        # The group name checks for the same thing as the user name
        assert regex_match(NAME_VALID, good_tests, bad_tests)

    def test_grouplist_simple(self):
        good_tests = [
                '',
                'gburdell',
                ' gburdell',
                ' \tgburdell',
                'gburdell ',
                'gburdell \t',
                '  gburdell  ',
                'gburdell,wheel',
                'gburdell, wheel',
                '  gburdell,  wheel',
                'gburdell,  wheel  ',
                '  gburdell,  wheel  ',
                'gburdell,  wheel',
                'gburdell,wheel, mock'
                ]

        bad_tests = [
                ',',
                '-invalid',
                'gburdell, -invalid',
                'gburdell,',
                'gburdell, ',
                ',gburdell',
                '  ,gburdell',
                ',gburdell,'
                'gburdell, wheel,'
                ]

        assert regex_match(GROUPLIST_SIMPLE_VALID, good_tests, bad_tests)
