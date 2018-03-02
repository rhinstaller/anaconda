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
from pyanaconda.modules.common.task.task import Task
from pyanaconda.modules.common.task.task_interface import TaskInterface

__all__ = ["publish_task", "Task", "TaskInterface"]


def publish_task(task_instance: Task, module_dbus_path):
    """Publish Task to the DBus.

    :param task_instance: Instance of a Task.
    :param module_dbus_path: DBus object path of a module.
    :type module_dbus_path: str
    """
    interface = TaskInterface(task_instance)
    interface.publish_from_module(module_dbus_path)
    return interface
