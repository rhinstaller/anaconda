# -*- coding: utf-8 -*-
#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>


import unittest
import os

from pyanaconda.ui.helpers import find_bootopt_mitigations, set_bootopt_mitigations

class BootoptMitigationsTests(unittest.TestCase):
    def find_bootopt_mitigations_test(self):
        """Check that options for disabling mitigations are detected correctly."""

        # empty string
        result = find_bootopt_mitigations("")
        self.assertFalse(result.no_pti)
        self.assertFalse(result.no_ibrs)
        self.assertFalse(result.no_ibpb)

        # single mitigation and random other options
        result = find_bootopt_mitigations("foo nopti bar")
        self.assertTrue(result.no_pti)
        self.assertFalse(result.no_ibrs)
        self.assertFalse(result.no_ibpb)

        # all mitigations set and random other options
        result = find_bootopt_mitigations("foo nopti bar noibrs noibpb baz")
        self.assertTrue(result.no_pti)
        self.assertTrue(result.no_ibrs)
        self.assertTrue(result.no_ibpb)

    def set_bootopt_mitigations_test(self):
        """Check that options for disabling mitigations are set correctly."""

        # not disabling any mitigations should not remove or add any options
        opts = set_bootopt_mitigations("", no_pti=False, no_ibrs=False, no_ibpb=False)
        self.assertIs(opts, "")
        opts = set(set_bootopt_mitigations("foo bar", no_pti=False, no_ibrs=False, no_ibpb=False).split(" "))
        self.assertIn("foo", opts)
        self.assertIn("bar", opts)
        self.assertNotIn("nopti", opts)
        self.assertNotIn("noibrs", opts)
        self.assertNotIn("noibpb", opts)

        # enable disabled mitigation
        opts = set(set_bootopt_mitigations("foo nopti bar", no_pti=False, no_ibrs=False, no_ibpb=False).split(" "))
        self.assertIn("foo", opts)
        self.assertIn("bar", opts)
        self.assertNotIn("nopti", opts)
        self.assertNotIn("noibrs", opts)
        self.assertNotIn("noibpb", opts)

        # disable already disabled mitigation
        opts = set(set_bootopt_mitigations("foo noibrs bar", no_pti=False, no_ibrs=True, no_ibpb=False).split(" "))
        self.assertIn("foo", opts)
        self.assertIn("bar", opts)
        self.assertIn("noibrs", opts)
        self.assertNotIn("nopti", opts)
        self.assertNotIn("noibpb", opts)

        # enable one disabled mitigation and disable two others
        opts = set(set_bootopt_mitigations("foo nopti bar", no_pti=False, no_ibrs=True, no_ibpb=True).split(" "))
        self.assertIn("foo", opts)
        self.assertIn("bar", opts)
        self.assertIn("noibrs", opts)
        self.assertIn("noibpb", opts)
        self.assertNotIn("nopti", opts)
