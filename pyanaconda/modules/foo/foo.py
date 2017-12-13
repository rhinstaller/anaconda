# foo.py
# Example DBUS module
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import MODULE_FOO_PATH, MODULE_FOO_NAME
from pyanaconda.modules.base import BaseModuleInterface
from pyanaconda.modules.foo.tasks.foo_task import FooTask
from pyanaconda.task import publish_task
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


@dbus_interface(MODULE_FOO_NAME)
class Foo(BaseModuleInterface):

    def __init__(self):
        super().__init__()
        self._task_interfaces = []

    def _collect_tasks(self):
        return [FooTask()]

    def publish(self):
        """Publish the module."""
        DBus.publish_object(self, MODULE_FOO_PATH)
        self.publish_tasks()
        DBus.register_service(MODULE_FOO_NAME)

    def EchoString(self, s: Str) -> Str:
        """Returns whatever is passed to it."""
        log.debug(s)
        return s

    def AvailableTasks(self) -> List[Tuple[Str, Str]]:
        ret = []

        for task in self._task_interfaces:
            ret.append((task.implementation.name, task.object_path))

        return ret

    def publish_tasks(self):
        for task in self._collect_tasks():
            self._task_interfaces.append(publish_task(task, MODULE_FOO_PATH))
