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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.task.task import AbstractTask

log = get_module_logger(__name__)

__all__ = ['DBusMetaTask']


class DBusMetaTask(AbstractTask):
    """A task that runs DBus tasks.

    FIXME: This class is not used anymore. Do we need it?
    """

    def __init__(self, name, tasks):
        """Create a new meta task.

        :param name: a name of the meta task
        :param tasks: a list of proxies to DBus tasks
        """
        super().__init__()
        self._name = name
        self._subtasks = tasks
        self._current_subtask = None
        self._total_steps = self._count_steps()
        self._finished_steps = 0

    @property
    def name(self):
        """Name of the meta task."""
        return self._name

    @property
    def steps(self):
        """Total number of progress steps."""
        return self._total_steps

    def _count_steps(self):
        """Return the total number of progress steps."""
        return sum(t.Steps for t in self._subtasks)

    @property
    def is_running(self):
        """Is the meta task running?"""
        return bool(self._current_subtask and self._current_subtask.IsRunning)

    def start(self):
        """Start the meta task."""
        log.info("'%s' has started.", self.name)
        self._task_started_callback()
        self._task_run_callback()

    def _task_run_callback(self):
        """Start the next task."""
        if self._current_subtask:
            self._disconnect(self._current_subtask)

        if self.check_cancel():
            log.info("'%s' is canceled.", self.name)
            self._task_stopped_callback()
            return

        if not self._subtasks:
            log.info("'%s' is complete.", self.name)
            self._task_succeeded_callback()
            self._task_stopped_callback()
            return

        self._current_subtask = self._subtasks.pop(0)
        self._connect(self._current_subtask)
        self._current_subtask.Start()

    def _connect(self, subtask):
        """Connect to signals of the current task."""
        subtask.Started.connect(self._subtask_started_callback)
        subtask.Failed.connect(self._subtask_failed_callback)
        subtask.Stopped.connect(self._subtask_stopped_callback)
        subtask.ProgressChanged.connect(self._subtask_progress_changed)

    def _disconnect(self, subtask):
        """Disconnect from signals of the previous task."""
        subtask.Started.disconnect()
        subtask.Failed.disconnect()
        subtask.Stopped.disconnect()
        subtask.ProgressChanged.disconnect()

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
        """Cancel the meta task."""
        super().cancel()

        if self._current_subtask:
            self._current_subtask.Cancel()

    def finish(self):
        """Finish the meta task.

        If the meta task failed, we should raise an error
        from the last running task.
        """
        if self._current_subtask:
            self._current_subtask.Finish()
