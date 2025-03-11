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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import math
from time import perf_counter, sleep

from pyanaconda.modules.common.task.task import AbstractTask, Task, ValidationTask
from pyanaconda.modules.common.task.task_interface import TaskInterface

__all__ = [
    "AbstractTask",
    "Task",
    "TaskInterface",
    "ValidationTask",
    "async_run_task",
    "sync_run_task",
    "wait_for_task",
]


def sync_run_task(task_proxy, callback=None):
    """Run a remote task synchronously.

    The given callback will be called every iteration.

    :param task_proxy: a proxy of the remote task
    :param callback: a callback
    :raise: a remote error
    """
    task_proxy.Start()

    while task_proxy.IsRunning:

        if callback:
            callback(task_proxy)

        sleep(0.1)

    task_proxy.Finish()


def async_run_task(task_proxy, callback):
    """Run a remote task asynchronously.

    The callback is called once the task is done. You should always
    call the Finish method of the remote task in your callback and
    handle the remote errors.

    Example of the callback:

        def callback(task_proxy):
            try:
                task_proxy.Finish()
            except RemoteError as e:
                pass

    :param task_proxy: a proxy of the remote task
    :param callback: a callback with a task_proxy argument
    """
    def _callback():
        callback(task_proxy)

    task_proxy.Stopped.connect(_callback)
    task_proxy.Start()


def wait_for_task(task_proxy, timeout=math.inf):
    """Wait for an existing and running task with optional timeout.

    If the timeout exception is raised, the task is not done. To call its Finish method and
    receive potential errors from its run, you can attach callbacks to the tasks's signals.
    Alternatively, you can give up re-raising the errors entirely.

    :param task_proxy: a proxy of the remote task
    :param float timeout: stop waiting after this time in seconds
    :raise TimeoutError: when the task did not finish before timeout
    """
    start = perf_counter()
    end = start + timeout

    while task_proxy.IsRunning and perf_counter() <= end:
        sleep(0.1)

    if task_proxy.IsRunning:
        raise TimeoutError()

    task_proxy.Finish()
