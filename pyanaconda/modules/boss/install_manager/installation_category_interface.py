# DBus installation task category interface.
#
# API specification of task category interface.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import TASK_CATEGORY
from pyanaconda.modules.common.task import TaskInterface

__all__ = ['CategoryReportTaskInterface']


@dbus_interface(TASK_CATEGORY.interface_name)
class CategoryReportTaskInterface(TaskInterface):
    "DBus interface for a task category report"

    def connect_signals(self):
        super().connect_signals()
        self.implementation.category_changed_signal.connect(self.CategoryChanged)

    @dbus_signal
    def CategoryChanged(self, category: Str):
        """Signal making progress for this task.

        :param category: Number of the category. See pyanaconda/core/constants.py
        InstallationCategories for info about a category indexes.
        """
        pass
