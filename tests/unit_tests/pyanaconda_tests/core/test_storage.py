#
# Copyright (C) 2022  Red Hat, Inc.
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
import unittest
from unittest.mock import patch

from blivet.size import Size
from bytesize import ROUND_HALF_UP, KiB

from pyanaconda.core.storage import suggest_swap_size


class StorageUtilsTests(unittest.TestCase):

    def _suggest_swap_size(self, *args, **kwargs):
        """Round the suggested swap size for easier comparison."""
        return suggest_swap_size(*args, **kwargs).round_to_nearest(KiB, ROUND_HALF_UP)

    @patch("pyanaconda.core.storage.total_memory")
    def test_suggest_swap_size(self, total_memory_getter):
        """Test the suggest_swap_size function."""
        total_memory_getter.return_value = Size("1 GiB")
        assert self._suggest_swap_size() == Size("2 GiB")

        total_memory_getter.return_value = Size("2 GiB")
        assert self._suggest_swap_size() == Size("2 GiB")

        total_memory_getter.return_value = Size("4 GiB")
        assert self._suggest_swap_size() == Size("4 GiB")

        total_memory_getter.return_value = Size("8 GiB")
        assert self._suggest_swap_size() == Size("4 GiB")

        total_memory_getter.return_value = Size("16 GiB")
        assert self._suggest_swap_size() == Size("8 GiB")

        total_memory_getter.return_value = Size("60 GiB")
        assert self._suggest_swap_size() == Size("30 GiB")

        total_memory_getter.return_value = Size("64 GiB")
        assert self._suggest_swap_size() == Size("32 GiB")

        total_memory_getter.return_value = Size("128 GiB")
        assert self._suggest_swap_size() == Size("32 GiB")

    @patch("pyanaconda.core.storage.total_memory")
    def test_suggest_swap_size_hibernation(self, total_memory_getter):
        """Test the suggest_swap_size function for hibernation."""
        total_memory_getter.return_value = Size("8 GiB")
        assert self._suggest_swap_size(hibernation=False) == Size("4 GiB")

        total_memory_getter.return_value = Size("8 GiB")
        assert self._suggest_swap_size(hibernation=True) == Size("12 GiB")

        total_memory_getter.return_value = Size("16 GiB")
        assert self._suggest_swap_size(hibernation=True) == Size("24 GiB")

        total_memory_getter.return_value = Size("64 GiB")
        assert self._suggest_swap_size(hibernation=True) == Size("32 GiB")

        total_memory_getter.return_value = Size("128 GiB")
        assert self._suggest_swap_size(hibernation=True) == Size("32 GiB")

    @patch("pyanaconda.core.storage.total_memory")
    def test_suggest_swap_size_disk_space(self, total_memory_getter):
        """Test the suggest_swap_size function for a specific disk space."""
        total_memory_getter.return_value = Size("8 GiB")

        assert self._suggest_swap_size(disk_space=Size("10 GiB")) == Size("1 GiB")
        assert self._suggest_swap_size(disk_space=Size("20 GiB")) == Size("2 GiB")
        assert self._suggest_swap_size(disk_space=Size("40 GiB")) == Size("4 GiB")
        assert self._suggest_swap_size(disk_space=Size("60 GiB")) == Size("4 GiB")
        assert self._suggest_swap_size(disk_space=None) == Size("4 GiB")
