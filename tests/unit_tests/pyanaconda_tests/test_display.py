#
# Copyright (C) 2026  Red Hat, Inc.
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
from unittest.mock import Mock, patch

import pytest

from pyanaconda import display


class StartupWLActionsTests(unittest.TestCase):
    """Test the compositor startup failure reporting."""

    def _run_startup(self, socket_exists, proc_running):
        """Run do_startup_wl_actions with a mocked environment."""
        childproc = Mock()
        childproc.poll.return_value = None if proc_running else 1

        with patch("pyanaconda.display.util.startProgram", return_value=childproc), \
             patch("pyanaconda.display.WatchProcesses") as watch, \
             patch("pyanaconda.display.journal.stream", return_value=None), \
             patch("pyanaconda.display._gnome_kiosk_supports_vt_switch",
                   return_value=False), \
             patch("pyanaconda.display.os.path.exists", return_value=socket_exists), \
             patch("pyanaconda.display.time.sleep"), \
             patch.dict(display.os.environ, {"XDG_RUNTIME_DIR": "/run/user/0"}):
            display.do_startup_wl_actions(1)
            return childproc, watch

    def test_socket_ready(self):
        """Return quietly when the compositor socket appears."""
        childproc, watch = self._run_startup(socket_exists=True, proc_running=True)
        watch.watch_process.assert_called_once()
        childproc.terminate.assert_not_called()

    def test_timeout_process_still_running(self):
        """A live compositor without a socket raises a timeout naming the state."""
        with pytest.raises(TimeoutError) as excinfo:
            self._run_startup(socket_exists=False, proc_running=True)

        assert "was still running" in str(excinfo.value)
        assert display.constants.WAYLAND_SOCKET_NAME in str(excinfo.value)

    def test_timeout_process_exited(self):
        """A dead compositor without a socket raises a timeout naming the exit."""
        with pytest.raises(TimeoutError) as excinfo:
            self._run_startup(socket_exists=False, proc_running=False)

        assert "had already exited" in str(excinfo.value)

    def test_timeout_terminates_and_unwatches(self):
        """The timed-out compositor is unwatched and terminated."""
        childproc = Mock()
        childproc.poll.return_value = None

        with patch("pyanaconda.display.util.startProgram", return_value=childproc), \
             patch("pyanaconda.display.WatchProcesses") as watch, \
             patch("pyanaconda.display.journal.stream", return_value=None), \
             patch("pyanaconda.display._gnome_kiosk_supports_vt_switch",
                   return_value=False), \
             patch("pyanaconda.display.os.path.exists", return_value=False), \
             patch("pyanaconda.display.time.sleep"), \
             patch.dict(display.os.environ, {"XDG_RUNTIME_DIR": "/run/user/0"}):
            with pytest.raises(TimeoutError):
                display.do_startup_wl_actions(1)

        watch.unwatch_process.assert_called_once_with(childproc)
        childproc.terminate.assert_called_once()


class CompositorJournalExcerptTests(unittest.TestCase):
    """Test the compositor journal excerpt helper."""

    @patch("pyanaconda.display.util.execWithCapture")
    def test_excerpt_printed(self, exec_mock):
        """A non-empty journal excerpt is printed with a pointer to the journal."""
        exec_mock.return_value = "kiosk: something broke"

        with patch("builtins.print") as print_mock:
            display._print_compositor_journal_excerpt()

        exec_mock.assert_called_once_with(
            "journalctl", ["-q", "-t", "gnome-kiosk", "-n", "15", "--no-pager"]
        )
        printed = "\n".join(str(c.args[0]) for c in print_mock.call_args_list if c.args)
        assert "kiosk: something broke" in printed
        assert "journalctl -t gnome-kiosk" in printed

    @patch("pyanaconda.display.util.execWithCapture")
    def test_journalctl_failure_is_not_fatal(self, exec_mock):
        """A failing journalctl must not raise; the pointer is still printed."""
        exec_mock.side_effect = OSError("no journalctl")

        with patch("builtins.print") as print_mock:
            display._print_compositor_journal_excerpt()

        printed = "\n".join(str(c.args[0]) for c in print_mock.call_args_list if c.args)
        assert "journalctl -t gnome-kiosk" in printed

    @patch("pyanaconda.display.util.execWithCapture")
    def test_empty_journal(self, exec_mock):
        """An empty journal prints only the pointer, not an empty excerpt block."""
        exec_mock.return_value = "\n"

        with patch("builtins.print") as print_mock:
            display._print_compositor_journal_excerpt()

        printed = [str(c.args[0]) for c in print_mock.call_args_list if c.args]
        assert not any("Last messages" in line for line in printed)
        assert any("journalctl -t gnome-kiosk" in line for line in printed)
