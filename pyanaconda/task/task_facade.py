# DBus Task facade.
#
# Hide DBus API from the rest of the program by hiding it behind facade class.
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

from pyanaconda.task.task import Task


class TaskFacade(object):

    def __init__(self, name, description, progress_steps_count):
        self._task_interface = Task()
        self._task_interface.set_name(name)
        self._task_interface.set_description(description)
        self._task_interface.set_progress_steps_count(progress_steps_count)

    def publish(self, dbus_name):
        self._task_interface.publish(dbus_name)

    @property
    def dbus_name(self):
        return self._task_interface.dbus_name

    @property
    def name(self):
        return self._task_interface.Name

    @property
    def description(self):
        return self._task_interface.Description

    @property
    def progress_steps_count(self):
        return self._task_interface.ProgressStepsCount

    @progress_steps_count.setter
    def progress_steps_count(self, progress_steps_count):
        self._task_interface.set_progress_steps_count(progress_steps_count)

    @property
    def progress(self):
        return self._task_interface.Progress

    def progress_changed(self, step, message):
        self._task_interface.progress_changed(step, message)

    @property
    def is_running(self):
        return self._task_interface.IsRunning

    def running_changed(self):
        self._task_interface.running_changed()

    def cancel(self):
        self._task_interface.Cancel()

    def check_cancel(self, clear=False):
        return self._task_interface.check_cancel(clear)

    def run(self):
        self._task_interface.set_task_job_callback(self.runnable)
        self._task_interface.Run()

    def runnable(self):
        pass
