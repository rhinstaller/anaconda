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
import pytest
import unittest

from time import sleep
from pyanaconda.threading import ThreadManager, AnacondaThread


class ThreadManagerTestCase(unittest.TestCase):
    """Test the thread manager."""

    def setUp(self):
        """Set up the test."""
        self._thread_manager = ThreadManager()

    @property
    def _thread_name(self):
        """Name of a testing thread."""
        return "TESTING_THREAD"

    def _thread_target(self):
        """Target of a testing thread."""
        sleep(1)

    @property
    def _thread(self):
        """Create a testing thread."""
        return AnacondaThread(
            name=self._thread_name,
            target=self._thread_target
        )

    @pytest.mark.xfail(raises=KeyError, reason="unresolved bug")
    def test_recreate_thread(self):
        """Try to create the same thread."""
        self._thread_manager.add(self._thread)
        self._thread_manager.wait(self._thread_name)
        self._thread_manager.add(self._thread)
