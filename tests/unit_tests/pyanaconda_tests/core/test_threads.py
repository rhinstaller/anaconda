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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import sys
import pytest
import unittest
from unittest.mock import patch

from time import sleep
from pyanaconda.core.threads import ThreadManager, AnacondaThread


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

    def test_add_thread(self):
        """Test basic thread creation and waiting."""
        with patch("pyanaconda.core.threads.thread_manager", new=self._thread_manager):
            self._thread_manager.add_thread(
                name="test_add_thread-1",
                target=self._thread_target
            )
            assert self._thread_manager.running == 1
            assert self._thread_manager.names == ["test_add_thread-1"]

            # now it's running
            thread = self._thread_manager.get("test_add_thread-1")
            assert thread.is_alive() is True

            # after waiting, it's not running and is removed
            self._thread_manager.wait("test_add_thread-1")
            assert thread.is_alive() is False
            assert self._thread_manager.running == 0
            assert self._thread_manager.names == []

            # now add more
            self._thread_manager.add_thread(
                name="test_add_thread-2",
                target=self._thread_target
            )
            self._thread_manager.add_thread(
                name="test_add_thread-3",
                target=self._thread_target
            )

            # must have only the new ones
            assert self._thread_manager.running == 2
            assert self._thread_manager.names == ["test_add_thread-2", "test_add_thread-3"]

            self._thread_manager.wait_all()
            assert self._thread_manager.any_errors is False

    def _thread_target_error(self):
        sleep(1)
        raise RuntimeError("Testing errors raised in threads")

    def test_thread_simple_errors(self):
        """Test normal thread error handling."""
        with patch("pyanaconda.core.threads.thread_manager", new=self._thread_manager):
            self._thread_manager.add_thread(
                name="test_thread_errors-1",
                target=self._thread_target
            )
            self._thread_manager.add_thread(
                name="test_thread_errors-2",
                target=self._thread_target_error
            )
            assert self._thread_manager.running == 2

            self._thread_manager.wait_all()
            # the error is "resolved" immediately and is no longer "active" at the end?
            assert self._thread_manager.any_errors is False

    def test_thread_fatal_errors(self):
        """Test thread fatal error handling.

            The errors happen in the thread, so catch them via an exception hook.
        """
        tb_info = None

        def exc_handler(exc_type, value, traceback):
            nonlocal tb_info
            tb_info = (exc_type, value, traceback)

        old_hook = sys.excepthook
        sys.excepthook = exc_handler

        with patch("pyanaconda.core.threads.thread_manager", new=self._thread_manager):
            self._thread_manager.add_thread(
                name="test_thread_errors-1",
                target=self._thread_target_error,
                fatal=True
            )
            assert self._thread_manager.running == 1
            self._thread_manager.wait_all()
            assert self._thread_manager.any_errors is False
            assert tb_info[0] == RuntimeError  # pylint: disable=unsubscriptable-object

        sys.excepthook = old_hook

    def test_wait_get_thread(self):
        """Test getting threads and waiting for threads"""
        with patch("pyanaconda.core.threads.thread_manager", new=self._thread_manager):
            self._thread_manager.add_thread(
                name="test_wait_thread-1",
                target=self._thread_target
            )
            assert isinstance(self._thread_manager.get("test_wait_thread-1"), AnacondaThread)
            # consecutive waits are ok, but the thread is done after first wait
            assert self._thread_manager.wait("test_wait_thread-1") is True
            assert self._thread_manager.wait("test_wait_thread-1") is False

            # waiting for a nonexistent thread is same as for done
            assert self._thread_manager.wait("test_wait_thread-nonexistent") is False


class AnacondaThreadTests(unittest.TestCase):
    """Tests for the AnacondaThread class"""
    def test_prefix(self):
        """Test automatic prefixes for threads."""
        for prefix in ("foo", "bar"):
            for i in range(3):
                t = AnacondaThread(
                    prefix=prefix,
                    target=None,
                )
                assert t.name == prefix + str(i+1)

    def test_auto_naming(self):
        """Test automatic naming of threads without name and prefix"""
        t = AnacondaThread()
        assert t.name == "AnaWorkerThread1"
