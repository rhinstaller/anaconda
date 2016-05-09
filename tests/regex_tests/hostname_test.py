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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Shea <dshea@redhat.com>
#
import unittest
import re

from regexcheck import regex_match
from pyanaconda.regexes import HOSTNAME_PATTERN_WITHOUT_ANCHORS, IPV4_PATTERN_WITHOUT_ANCHORS

class HostnameRegexTestCase(unittest.TestCase):
    def hostname_test(self):
        good_tests = [
                '0',
                'a',
                'A',
                'hostname',
                'host-name',
                'host.name',
                'host.name.with.oneverylongsectionthatisexactly63characterslong-and-contains-se',
                '3numberstart',
                'numberend3',
                'first.3numberstart',
                'first.3numberend',
                'dot.end.'
                ]

        bad_tests = [
                '.',
                '..',
                'too..many.dots',
                '-hypenstart',
                'hyphenend-',
                'first.-hyphenstart',
                'first.hyphenend-',
                'bad,character',
                '.dot.start',
                'host.name.with.oneverylongsectionthatisexactly64characterslong-and-contains-sev',
                'únicode'
                ]

        hostname_re = re.compile('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$')
        if not regex_match(hostname_re, good_tests, bad_tests):
            self.fail()

class IPv4RegexTestCase(unittest.TestCase):
    def ipv4_test(self):
        good_tests = [
                '1.2.3.4',
                '0.0.0.0',
                '10.20.30.40',
                '255.255.255.255',
                '249.249.249.249'
                ]

        bad_tests = [
                '1.2.3.',
                '1.2.3',
                '256.2.3.4',
                'a.b.c.d',
                '1.2.3.400'
                '....',
                '1..2.3'
                ]

        ipv4_re = re.compile('^(' + IPV4_PATTERN_WITHOUT_ANCHORS + ')$')
        if not regex_match(ipv4_re, good_tests, bad_tests):
            self.fail()
