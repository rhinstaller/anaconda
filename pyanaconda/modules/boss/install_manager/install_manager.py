# Handle installation tasks from modules.
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

from pyanaconda.core.signal import Signal
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.errors.installation import InstallationNotRunning

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

TASK_NAME = 0
TASK_PATH = 1


class InstallManager(object):
    """Manager to control module installation.

    Installation tasks will be collected from modules and run one by one.

    Provides summarized API (InstallationInterface class) for UI.
    """

    def __init__(self):
        """ Create installation manager."""
        self._tasks = set()
        self._actual_task = None
        self._step_sum = 0
        self._tasks_done_step = 0
        self._installation_terminated = False
        self._module_observers = []

        self._install_started_signal = Signal()
        self._install_stopped_signal = Signal()
        self._task_changed_signal = Signal()
        self._progress_changed_signal = Signal()
        self._progress_changed_float_signal = Signal()
        self._error_raised_signal = Signal()

        self._subscriptions = []

    @property
    def installation_started(self):
        return self._install_started_signal

    @property
    def installation_stopped(self):
        return self._install_stopped_signal

    @property
    def task_changed_signal(self):
        """Signal when installation task changed."""
        return self._task_changed_signal

    @property
    def progress_changed_signal(self):
        """Signal when progress changed."""
        return self._progress_changed_signal

    @property
    def progress_changed_float_signal(self):
        """Signal when progress in float changed."""
        return self._progress_changed_float_signal

    @property
    def error_raised_signal(self):
        """Signal which will be emitted when error raised during installation."""
        return self._error_raised_signal

    @property
    def module_observers(self):
        """Get all module observers which will be used for installation."""
        return self._module_observers

    @module_observers.setter
    def module_observers(self, modules):
        """Set module observers which will be used for installation.

        :param modules: Module observers list.
        :type modules: list
        """
        self._module_observers = modules

    def start_installation(self):
        """Start the installation."""
        self._collect_tasks()

        self._sum_steps_count()
        self._disconnect_task()
        self._tasks_done_step = 0
        self._installation_terminated = False

        if self._tasks:
            self._actual_task = self._tasks.pop()
            self._install_started_signal.emit()
            self._run_task()

    def _collect_tasks(self):
        self._tasks.clear()

        if not self._module_observers:
            log.error("Starting installation without available modules.")

        for observer in self._module_observers:
            # FIXME: This check is here for testing purposes only.
            # Normally, all given modules should be available once
            # we start the installation.
            if not observer.is_service_available:
                log.error("Module %s is not available!", observer.service_name)
                continue

            tasks = observer.proxy.AvailableTasks
            for task in tasks:
                log.debug("Getting task %s from module %s", task[TASK_NAME], observer.service_name)
                task_proxy = DBus.get_proxy(observer.service_name, task[TASK_PATH])
                self._tasks.add(task_proxy)

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
        self._task_changed_signal.emit(task_name)
        self._actual_task.Start()

    def _connect_task(self):
        s = self._actual_task.ProgressChanged.connect(self._progress_changed)
        self._subscriptions.append(s)

        s = self._actual_task.Started.connect(self._task_started)
        self._subscriptions.append(s)

        s = self._actual_task.Stopped.connect(self._task_stopped)
        self._subscriptions.append(s)

        s = self._actual_task.ErrorRaised.connect(self._task_error_raised)
        self._subscriptions.append(s)

    def _disconnect_task(self):
        for subscription in self._subscriptions:
            subscription.disconnect()

    def _test_if_running(self, log_msg=None):
        if self._actual_task is not None:
            return True
        else:
            log.warning(log_msg)
            return False

    def _task_stopped(self):
        self._tasks_done_step += self._actual_task.ProgressStepsCount
        if self._tasks:
            self._actual_task = self._tasks.pop()
            self._run_task()
        else:
            log.info("Installation finished.")
            self._actual_task = None
            self._install_stopped_signal.emit()

    def _task_started(self):
        log.info("Installation task %s has started.", self._actual_task)

    def _task_error_raised(self, error_description):
        self._error_raised_signal.emit(error_description)

    @property
    def installation_running(self):
        """Installation is running right now.

        :returns: True if installation is running. False otherwise.
        """
        return self._actual_task is not None

    @property
    def task_name(self):
        """Get name of the running task."""
        if self._test_if_running("Can't get task name when installation is not running."):
            return self._actual_task.Name
        else:
            return ""

    @property
    def task_description(self):
        """Get description of the running task."""
        if self._test_if_running("Can't get task description when installation is not running."):
            return self._actual_task.Description
        else:
            return ""

    @property
    def progress_steps_count(self):
        """Sum of steps in all tasks used for installation."""
        if self._test_if_running("Can't get sum of all tasks when installation is not running."):
            return self._step_sum
        else:
            return 0

    def _progress_changed(self, step, msg):
        actual_progress = step + self._tasks_done_step
        self._progress_changed_signal.emit(actual_progress, msg)
        self._progress_changed_float_signal.emit(actual_progress / self._step_sum, msg)

    @property
    def progress(self):
        """Get progress of the installation.

        :returns: (step: int, msg: str) tuple.
                  step - step in the installation process.
                  msg - short description of the step
        """
        if self._test_if_running("Can't get task progress when installation is not running."):
            (step, msg) = self._actual_task.Progress
            actual_progress = step + self._tasks_done_step

            return actual_progress, msg
        else:
            return 0, ""

    @property
    def progress_float(self):
        """Get progress of the installation as float number from 0.0 to 1.0.

        :returns: (step: float, msg: str) tuple.
                  step - step in the installation process.
                  msg - short description of the step
        """
        if self._test_if_running("Can't get task progress in float "
                                 "when installation is not running."):
            (step, msg) = self._actual_task.Progress
            actual_progress = step + self._tasks_done_step
            actual_progress = actual_progress / self._step_sum

            return actual_progress, msg
        else:
            return 0, ""

    def cancel(self):
        """Cancel installation.

        Installation will be canceled as soon as possible. When exactly depends on the actual task
        running.
        """
        if self._test_if_running():

            self._installation_terminated = True

            if self._actual_task.IsCancelable:
                self._actual_task.Cancel()
        else:
            raise InstallationNotRunning("Can't cancel task when installation is not running.")
