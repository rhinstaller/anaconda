#
# Shared installation progress error handling for GUI and TUI.
#
# Copyright (C) 2026  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.errors import errorHandler
from pyanaconda.modules.common.constants.installation import InstallationErrorDialogType

log = get_module_logger(__name__)


class InstallationProgressErrorMixin:
    """Handle installation errors forwarded from the Boss process over D-Bus."""

    def _on_error_raised(self, message, detail_type):
        """Handle an error that needs user interaction.

        Show the error message dialog and send the user's response back to the
        Boss process so the installation task queue can continue or abort.

        :param message: the error message to display
        :param detail_type: an InstallationErrorDialogType value
        """
        try:
            dialog_type = InstallationErrorDialogType(detail_type)
        except ValueError:
            log.error("Unknown installation error dialog type: %r", detail_type)
            self._task_proxy.RespondToError(False)
            return

        if dialog_type == InstallationErrorDialogType.FATAL_ERROR:
            errorHandler.ui.showError(message)
            self._task_proxy.RespondToError(False)
        elif dialog_type == InstallationErrorDialogType.YES_NO:
            answer = errorHandler.ui.showYesNoQuestion(message)
            self._task_proxy.RespondToError(answer)
