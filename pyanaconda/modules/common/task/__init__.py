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
from time import sleep

from pyanaconda.modules.common.task.task_interface import TaskInterface
from pyanaconda.modules.common.task.task import Task, AbstractTask
from pyanaconda.modules.common.task.meta import DBusMetaTask

__all__ = ["sync_run_task", "async_run_task", "AbstractTask", "Task", "TaskInterface",
           "DBusMetaTask"]


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

        sleep(1)

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
