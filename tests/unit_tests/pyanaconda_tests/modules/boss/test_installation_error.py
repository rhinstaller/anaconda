# Test installation error forwarding from Boss to the UI.
#
# Copyright (C) 2026 Red Hat, Inc.
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
from unittest.mock import Mock

from pyanaconda.errors import ERROR_RAISE, ScriptError, errorHandler
from pyanaconda.installation_tasks import Task, TaskQueue
from pyanaconda.modules.boss.installation import RunInstallationTask, _RemoteErrorUI
from pyanaconda.modules.common.constants.installation import InstallationErrorDialogType
from pyanaconda.modules.common.errors.installation import NonCriticalInstallationError


class TestRunInstallationWithErrors(RunInstallationTask):
    """RunInstallationTask with minimal queues for error handler tests."""

    def _make_queue(self, name, tasks):
        queue = TaskQueue(name)
        queue.queue_started.connect(self._queue_started_cb)
        queue.task_completed.connect(self._task_completed_cb)
        for task_name, cb in tasks:
            queue.append(Task(task_name, cb))
        return queue

    def _prepare_installation(self):
        return self._make_queue("Installation queue", [("No-op", lambda: None)])

    def _prepare_configuration(self):
        return self._make_queue("Configuration queue", [("No-op", lambda: None)])


class InstallationErrorHandlerTestCase(unittest.TestCase):
    """Test errorHandler integration with the remote UI during installation."""

    def setUp(self):
        self.previous_ui = errorHandler.ui

    def tearDown(self):
        errorHandler.ui = self.previous_ui

    def test_non_critical_error_forwarded_during_installation(self):
        """Non-critical errors during installation are forwarded to the UI."""
        task = TestRunInstallationWithErrors(Mock())
        received = []

        def handler(message, detail_type):
            received.append((message, detail_type))
            task.respond_to_error(True)

        task.error_raised_signal.connect(handler)

        def raise_error():
            raise NonCriticalInstallationError("queue error")

        task._prepare_installation = lambda: task._make_queue(
            "Installation queue",
            [("Raise non-critical error", raise_error)],
        )

        task.run()

        assert len(received) == 1
        assert received[0][1] == InstallationErrorDialogType.YES_NO.value
        assert "queue error" in received[0][0]

    def test_script_error_uses_fatal_dialog(self):
        """Script errors are forwarded as fatal error dialogs."""
        task = RunInstallationTask(Mock())
        received = []

        def handler(message, detail_type):
            received.append((message, detail_type))
            task.respond_to_error(False)

        task.error_raised_signal.connect(handler)
        errorHandler.ui = _RemoteErrorUI(task)

        result = errorHandler.cb(ScriptError(42, "script failed"))

        assert result == ERROR_RAISE
        assert len(received) == 1
        assert received[0][1] == InstallationErrorDialogType.FATAL_ERROR.value
        assert "42" in received[0][0]
        assert "script failed" in received[0][0]
