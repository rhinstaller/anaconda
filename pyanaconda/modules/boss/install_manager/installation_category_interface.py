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
        self.watch_property("CurrentCategory", self.implementation.category_changed_signal)
        self.implementation.category_changed_signal.connect(self.flush_changes)
        self.implementation.error_raised_signal.connect(self.ErrorRaised)

    @property
    def CurrentCategory(self) -> Str:
        """Get the current installation category.

        :returns: the name of the current category, or an empty string.
        """
        return self.implementation.current_category

    @dbus_signal
    def ErrorRaised(self, message: Str, detail_type: Str):
        """Signal emitted when an error needs user interaction.

        The UI should show the error message to the user and call
        RespondToError with the user's response.

        :param message: the error message to display
        :param detail_type: an InstallationErrorDialogType value
        """
        pass

    def RespondToError(self, should_continue: Bool):
        """Respond to a previously emitted ErrorRaised signal.

        :param should_continue: True to continue, False to abort.
        """
        self.implementation.respond_to_error(should_continue)
