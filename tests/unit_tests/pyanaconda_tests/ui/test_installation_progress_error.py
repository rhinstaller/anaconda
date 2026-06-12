# Test shared installation progress error handling.
#
# Copyright (C) 2026 Red Hat, Inc.
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
import unittest
from unittest.mock import Mock, patch

from pyanaconda.modules.common.constants.installation import InstallationErrorDialogType
from pyanaconda.ui.lib.installation_progress_error import InstallationProgressErrorMixin


class _TestProgressSpoke(InstallationProgressErrorMixin):
    """Minimal spoke using the shared error handling mixin."""

    def __init__(self):
        self._task_proxy = Mock()


class InstallationProgressErrorMixinTestCase(unittest.TestCase):
    """Test InstallationProgressErrorMixin."""

    @patch("pyanaconda.ui.lib.installation_progress_error.errorHandler")
    def test_on_error_raised(self, mocked_error_handler):
        """Fatal and yes/no errors use the right dialog and response."""
        spoke = _TestProgressSpoke()
        mock_ui = Mock()
        mocked_error_handler.ui = mock_ui
        mock_ui.showYesNoQuestion.return_value = True

        spoke._on_error_raised("Installation failed", InstallationErrorDialogType.FATAL_ERROR.value)
        mock_ui.showError.assert_called_once_with("Installation failed")
        spoke._task_proxy.RespondToError.assert_called_with(False)

        mock_ui.reset_mock()
        spoke._task_proxy.reset_mock()

        spoke._on_error_raised("Ignore this error?", InstallationErrorDialogType.YES_NO.value)
        mock_ui.showYesNoQuestion.assert_called_once_with("Ignore this error?")
        spoke._task_proxy.RespondToError.assert_called_once_with(True)

        mock_ui.reset_mock()
        spoke._task_proxy.reset_mock()

        spoke._on_error_raised("Unexpected", "invalid")
        mock_ui.showError.assert_not_called()
        mock_ui.showYesNoQuestion.assert_not_called()
        spoke._task_proxy.RespondToError.assert_called_once_with(False)
