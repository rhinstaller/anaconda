#!/usr/bin/python
#
# tests/storage/size_tests.py
# Size test cases for the pyanaconda.storage module
#
# Copyright (C) 2010  Red Hat, Inc.
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
# Red Hat Author(s): David Cantrell <dcantrell@redhat.com>

import unittest

from pyanaconda import anaconda_log
anaconda_log.init()
from pyanaconda.storage.errors import *
from pyanaconda.storage.size import Size, _prefixes

class SizeTestCase(unittest.TestCase):
    def testExceptions(self):
        self.assertRaises(SizeParamsError, Size)
        self.assertRaises(SizeParamsError, Size, bytes=500, spec="45GB")

        self.assertRaises(SizeNotPositiveError, Size, bytes=-1)

        self.assertRaises(SizeNotPositiveError, Size, spec="0")
        self.assertRaises(SizeNotPositiveError, Size, spec="-1 TB")
        self.assertRaises(SizeNotPositiveError, Size, spec="-47kb")

        s = Size(bytes=500)
        self.assertRaises(SizePlacesError, s.humanReadable, places=0)

    def _prefixTestHelper(self, bytes, factor, prefix, abbr):
        c = bytes * factor

        s = Size(bytes=c)
        self.assertEquals(s, c)

        if prefix:
            u = "%sbytes" % prefix
            s = Size(spec="%ld %s" % (bytes, u))
            self.assertEquals(s, c)
            self.assertEquals(s.convertTo(spec=u), bytes)

        if abbr:
            u = "%sb" % abbr
            s = Size(spec="%ld %s" % (bytes, u))
            self.assertEquals(s, c)
            self.assertEquals(s.convertTo(spec=u), bytes)

        if not prefix and not abbr:
            s = Size(spec="%ld" % bytes)
            self.assertEquals(s, c)
            self.assertEquals(s.convertTo(), bytes)

    def testPrefixes(self):
        bytes = 47L
        self._prefixTestHelper(bytes, 1, None, None)

        for factor, prefix, abbr in _prefixes:
            self._prefixTestHelper(bytes, factor, prefix, abbr)

    def testHumanReadable(self):
        s = Size(bytes=58929971L)
        self.assertEquals(s.humanReadable(), "58.9 Mb")

        s = Size(bytes=478360371L)
        self.assertEquals(s.humanReadable(), "0.48 Gb")

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(SizeTestCase)

if __name__ == "__main__":
    unittest.main()
