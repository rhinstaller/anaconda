#
# The main installation task
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pyanaconda.modules.common.task import AbstractTask

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ['SystemInstallationTask']


class SystemInstallationTask(AbstractTask):

    def __init__(self, installation_tasks):
        super().__init__()
        self._subtasks = installation_tasks
        self._current_subtask = None
        self._subscriptions = []
        self._total_steps = self._count_steps()
        self._finished_steps = 0

    @property
    def name(self):
        return "Install the system"

    @property
    def steps(self):
        """Total number of progress steps."""
        return self._total_steps

    def _count_steps(self):
        """Return the total number of progress steps."""
        return sum(t.Steps for t in self._subtasks)

    @property
    def is_running(self):
        """Is the installation running?"""
        return bool(self._current_subtask and self._current_subtask.IsRunning)

    def start(self):
        """Start the installation."""
        log.info("Installation has started.")
        self._task_started_callback()
        self._task_run_callback()

    def _task_run_callback(self):
        """Start the next installation task."""
        self._disconnect_all()

        if not self._subtasks:
            log.info("Installation is complete.")
            self._task_stopped_callback()
            return

        if self.check_cancel():
            log.info("Installation is canceled.")
            self._task_stopped_callback()
            return

        self._current_subtask = self._subtasks.pop(0)
        self._connect(self._current_subtask)
        self._current_subtask.Start()

    def _connect(self, subtask):
        """Connect to signals of the current task."""
        s = subtask.Started.connect(self._subtask_started_callback)
        self._subscriptions.append(s)

        s = subtask.Failed.connect(self._subtask_failed_callback)
        self._subscriptions.append(s)

        s = subtask.Stopped.connect(self._subtask_stopped_callback)
        self._subscriptions.append(s)

        s = subtask.ProgressChanged.connect(self._subtask_progress_changed)
        self._subscriptions.append(s)

    def _disconnect_all(self):
        """Disconnect from all signals of the previous task."""
        while self._subscriptions:
            s = self._subscriptions.pop(0)
            s.disconnect()

    def _subtask_started_callback(self):
        log.info("'%s' has started.", self._current_subtask.Name)

    def _subtask_failed_callback(self):
        log.info("'%s' has failed.", self._current_subtask.Name)
        self._task_failed_callback()
        self.cancel()

    def _subtask_stopped_callback(self):
        log.info("'%s' has stopped.", self._current_subtask.Name)
        self._finished_steps += self._current_subtask.Steps
        self._task_run_callback()

    def _subtask_progress_changed(self, step, msg):
        log.debug("%s (%s/%s)", msg, step, self.steps)
        self.report_progress(msg, step_number=self._finished_steps + step)

    def cancel(self):
        """Cancel the installation."""
        super().cancel()

        if self._current_subtask:
            self._current_subtask.Cancel()

    def finish(self):
        """Finish the installation.

        If the installation failed, we should raise an error
        from the last running installation task.
        """
        if self._current_subtask:
            self._current_subtask.Finish()
