# Handle installation tasks from modules
#
# Copyright (C) 2017 Red Hat, Inc.
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

from pyanaconda.dbus import get_bus
from pyanaconda.modules.boss.install_manager.installation_interface import InstallationNotRunning

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)

TASK_NAME = 0
TASK_PATH = 1


class InstallManager(object):
    """Manager to control module installation.

    Installation tasks will be collected from modules and run one by one.

    Provides summarized API (InstallationInterface class) for UI.
    """

    def __init__(self, modules):
        """ Create installation manager.

        :param modules: Modules provided by boss to collect installation tasks.
        """
        self._bus = get_bus()
        self._tasks = self._collect_tasks(modules)
        self._actual_task = None
        self._step_sum = 0
        self._tasks_done_step = 0
        self._installation_terminated = False

        self._installation_running_signal = None
        self._task_changed_signal = None
        self._progress_signal = None
        self._progress_float_signal = None

        self._subscriptions = []

    def _collect_tasks(self, modules):
        ret_tasks = []

        for module_object in modules:
            tasks = module_object.AvailableTasks()
            for task in tasks:
                log.debug("Getting task %s from module %s", task[TASK_NAME], module_object.dbus_name)
                task_proxy = self._bus.get(task[TASK_PATH])
                ret_tasks.append(task_proxy)

        return ret_tasks

    def set_installation_running_changed_signal(self, running_changed):
        """Set signal from interface when installation stops."""
        self._installation_running_signal = running_changed

    def set_task_changed_signal(self, task_changed):
        """Set signal from interface when task changed."""
        self._task_changed_signal = task_changed

    def set_progress_changed_signal(self, progress_changed):
        """Set signal from interface when progress changed."""
        self._progress_signal = progress_changed

    def set_progress_float_changed_signal(self, progress_float_changed):
        """Set signal from interface when progress in float changed."""
        self._progress_float_signal = progress_float_changed

    def start_installation(self):
        """Start the installation."""
        self._sum_steps_count()
        self._disconnect_task()
        self._tasks_done_step = 0
        self._installation_terminated = False

        self._actual_task = self._tasks.pop()
        self._installation_running_signal(True)
        self._run_task()

    def _sum_steps_count(self):
        self._step_sum = 0
        for task in self._tasks:
            self._step_sum += task.ProgressStepsCount

    def _run_task(self):
        if self._installation_terminated:
            log.debug("Don't run another task. The installation was terminated.")
            return

        task_name = self._actual_task.Name

        log.debug("Running installation task %s", task_name)
        self._disconnect_task()
        self._connect_task()
        self._task_changed_signal(task_name)
        self._actual_task.Run()

    def _connect_task(self):
        s = self._actual_task.ProgressChanged.connect(self._progress_changed)
        self._subscriptions.append(s)

        s = self._actual_task.RunningChanged.connect(self._task_running_changed)
        self._subscriptions.append(s)

    def _disconnect_task(self):
        for subscription in self._subscriptions:
            subscription.disconnect()

    def _test_if_running(self, error_msg):
        if self._tasks_done_step is None:
            raise InstallationNotRunning(error_msg)

    def _task_running_changed(self, is_running):
        if not is_running:
            self._tasks_done_step += self._actual_task.ProgressStepsCount
            if self._tasks:
                self._actual_task = self._tasks.pop()
                self._run_task()
            else:
                log.info("Installation finished.")
                self._actual_task = None
                self._installation_running_signal(False)

    @property
    def installation_running(self):
        """Installation is running right now.

        :returns: True if installation is running. False otherwise.
        """
        return self._actual_task is not None

    @property
    def task_name(self):
        """Get name of the running task."""
        self._test_if_running("Can't get task name when installation is not running.")
        return self._actual_task.Name

    @property
    def task_description(self):
        """Get description of the running task."""
        self._test_if_running("Can't get task description when installation is not running.")
        return self._actual_task.Description

    def _progress_changed(self, step, msg):
        actual_progress = step + self._tasks_done_step
        self._progress_signal(actual_progress, msg)
        self._progress_float_signal(actual_progress / self._step_sum, msg)

    @property
    def progress(self):
        """Get progress of the installation.

        :returns: (step: int, msg: str) tuple.
                  step - step in the installation process.
                  msg - short description of the step
        """
        self._test_if_running("Can't get task progress when installation is not running.")
        (step, msg) = self._actual_task.Progress
        actual_progress = step + self._tasks_done_step

        return actual_progress, msg

    @property
    def progress_float(self):
        """Get progress of the installation as float number from 0.0 to 1.0.

        :returns: (step: float, msg: str) tuple.
                  step - step in the installation process.
                  msg - short description of the step
        """
        self._test_if_running("Can't get task progress in float when installation is not running.")
        (step, msg) = self._actual_task.Progress
        actual_progress = step + self._tasks_done_step
        actual_progress = actual_progress / self._step_sum

        return actual_progress, msg

    def cancel(self):
        """Cancel installation.

        Installation will be canceled as soon as possible. When exactly depends on the actual task
        running.
        """
        self._test_if_running("Can't cancel task when installation is not running.")

        self._installation_terminated = True

        if self._actual_task.IsCancelable:
            self._actual_task.Cancel()
