# DBus Task for Bar example modules.
#
# Example of Task using interface as instance.
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

import time
from pyanaconda.task.task import Task


class FooTask(object):

    def __init__(self):
        self._task_interface = Task()

    @property
    def name(self):
        return self._task_interface.Name

    def publish(self, dbus_module_name):
        self._task_interface.publish(dbus_module_name)

    @property
    def dbus_name(self):
        return self._task_interface.dbus_name

    def run(self):
        self._task_interface.set_task_job_callback(self._runnable)
        self._task_interface.Run()

    def _runnable(self):
        """This is run on separate thread."""
        self._task_interface.progress_changed(1, "preparing for the hard work -- better than Bar")

        # preparing deck for play...
        time.sleep(1)

        if self._task_interface.check_cancel():
            return

        self._task_interface.progress_changed(2, "loosing strength...")
        # playing online games...
        time.sleep(1)

        if self._task_interface.check_cancel():
            return

        self._task_interface.progress_changed(3, "Having hard time to continue...")
        # playing MMORPG...
        time.sleep(1)

        if self._task_interface.check_cancel():
            return

        self._task_interface.progress_changed(4, "Almost unbearable...")
        # returning from walk and pretending work...
        time.sleep(1)

        self._task_interface.progress_changed(5, "Hard work is done")
