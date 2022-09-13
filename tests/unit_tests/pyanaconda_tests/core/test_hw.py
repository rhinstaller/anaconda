# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
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

import unittest
from unittest.mock import patch
import pytest
from textwrap import dedent
from io import StringIO

from pyanaconda.core.hw import total_memory

class MemoryTests(unittest.TestCase):

    MEMINFO = dedent(
        """MemTotal:       32526648 kB
           MemFree:         8196560 kB
           MemAvailable:   21189232 kB
           Buffers:            4012 kB
           Cached:         13974708 kB
           SwapCached:            0 kB
           Active:          4934172 kB
           Inactive:       17128972 kB
           Active(anon):       7184 kB
           Inactive(anon):  9202192 kB
           Active(file):    4926988 kB
           Inactive(file):  7926780 kB
           Unevictable:     1009932 kB
           Mlocked:             152 kB
           SwapTotal:       8388604 kB
           SwapFree:        8388604 kB
           Zswap:                 0 kB
           Zswapped:              0 kB
           Dirty:              4508 kB
           Writeback:             0 kB
           AnonPages:       9094440 kB
           Mapped:          1224920 kB
           Shmem:           1124952 kB
           KReclaimable:     605048 kB
           Slab:             969324 kB
           SReclaimable:     605048 kB
           SUnreclaim:       364276 kB
           KernelStack:       36672 kB
           PageTables:        85696 kB
           NFS_Unstable:          0 kB
           Bounce:                0 kB
           WritebackTmp:          0 kB
           CommitLimit:    24651928 kB
           Committed_AS:   19177064 kB
           VmallocTotal:   34359738367 kB
           VmallocUsed:      102060 kB
           VmallocChunk:          0 kB
           Percpu:            11392 kB
           HardwareCorrupted:     0 kB
           AnonHugePages:         0 kB
           ShmemHugePages:        0 kB
           ShmemPmdMapped:        0 kB
           FileHugePages:         0 kB
           FilePmdMapped:         0 kB
           CmaTotal:              0 kB
           CmaFree:               0 kB
           HugePages_Total:       0
           HugePages_Free:        0
           HugePages_Rsvd:        0
           HugePages_Surp:        0
           Hugepagesize:       2048 kB
           Hugetlb:               0 kB
           DirectMap4k:      829716 kB
           DirectMap2M:    27138048 kB
           DirectMap1G:     6291456 kB
        """
    )

    @patch("pyanaconda.core.hw.open")
    def test_total_memory_real(self, open_mock):
        """Test total_memory with real data"""
        open_mock.return_value = StringIO(self.MEMINFO)
        assert total_memory() == 32657720.0
        open_mock.assert_called_once_with("/proc/meminfo", "r")

    @patch("pyanaconda.core.hw.open")
    def test_total_memory_missing(self, open_mock):
        """Test total_memory with missing value"""
        missing = self.MEMINFO.replace("MemTotal", "Nonsense")
        open_mock.return_value = StringIO(missing)
        with pytest.raises(RuntimeError):
            total_memory()
        open_mock.assert_called_once_with("/proc/meminfo", "r")

    @patch("pyanaconda.core.hw.open")
    def test_total_memory_not_number(self, open_mock):
        """Test total_memory with bad format"""
        missing = self.MEMINFO.replace(
            "MemTotal:       32526648 kB",
            "MemTotal:       nonsense kB"
        )
        open_mock.return_value = StringIO(missing)
        with pytest.raises(RuntimeError):
            total_memory()

        malformed = self.MEMINFO.replace(
            "MemTotal:       32526648 kB",
            "MemTotal:       32526648 kB as of right now"
        )
        open_mock.return_value = StringIO(malformed)
        with pytest.raises(RuntimeError):
            total_memory()

    @patch("pyanaconda.core.hw.open")
    def test_total_memory_calculations(self, open_mock):
        """Test total_memory calculates correctly."""
        open_mock.return_value = StringIO("MemTotal: 1024 kB")
        assert total_memory() == 132096.0

        open_mock.return_value = StringIO("MemTotal: 65536 kB")
        assert total_memory() == 196608.0

        open_mock.return_value = StringIO("MemTotal: 10000000 kB")
        assert total_memory() == 10131072.0
