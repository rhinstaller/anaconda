#!/usr/bin/python3
# vim:set fileencoding=utf-8
#
# Copyright (C) 2014  Red Hat, Inc.
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
from pyanaconda.core.regexes import REPO_NAME_VALID

class RepoNameTestCase(unittest.TestCase):
    def test_reponame(self):
        good_tests = [
                'reponame',
                'repoName',
                'repo-name',
                'repo.name',
                'repo_name',
                'repo:name',
                'rep0Name',
                '0repoName',
                'repoName0'
                ]

        bad_tests = [
                'repo name',
                'répo name',
                '@repo name',
                '[reponame]'
                ]

        assert regex_match(REPO_NAME_VALID, good_tests, bad_tests)
