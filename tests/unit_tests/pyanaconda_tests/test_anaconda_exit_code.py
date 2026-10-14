#
# Copyright (C) 2026  Red Hat, Inc.
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
from unittest.mock import Mock, patch

import pytest

from pyanaconda.installation_outcome import installation_outcome
from pyanaconda.modules.common.constants.installation import (
    InstallationFailureReason,
    InstallationStatus,
)

anaconda = pytest.importorskip("anaconda")


class DetermineExitCodeTestCase:

    @pytest.mark.parametrize("status", [
        InstallationStatus.FAILED,
        InstallationStatus.ABORTED,
        InstallationStatus.RUNNING,
    ])
    def test_non_success_is_nonzero(self, status):
        boss_proxy = Mock(
            InstallationStatus=status.value,
            InstallationFailureReason="unhandled_exception",
        )
        assert anaconda.determine_exit_code(boss_proxy) == 1

    def test_success_is_zero(self):
        boss_proxy = Mock(
            InstallationStatus=InstallationStatus.SUCCEEDED.value,
            InstallationFailureReason="none",
        )
        assert anaconda.determine_exit_code(boss_proxy) == 0

    def test_not_started_is_zero(self):
        """No installation was attempted (e.g. rescue mode) -- not a failure."""
        boss_proxy = Mock(
            InstallationStatus=InstallationStatus.NOT_STARTED.value,
            InstallationFailureReason="none",
        )
        assert anaconda.determine_exit_code(boss_proxy) == 0


class ExitHandlerTestCase:

    def setup_method(self):
        installation_outcome.reporting_started = False

    def teardown_method(self):
        installation_outcome.reporting_started = False

    def test_exit_handler_reports_unreported_outcome(self):
        """The exit handler reports an outcome nobody else reported yet."""
        boss_proxy = Mock(
            InstallationStatus=InstallationStatus.FAILED.value,
            InstallationFailureReason=InstallationFailureReason.UNHANDLED_EXCEPTION.value,
        )
        boss_cls = Mock()
        boss_cls.get_proxy.return_value = boss_proxy

        with patch("pyanaconda.modules.common.constants.services.BOSS", boss_cls), \
                patch("pyanaconda.installation_outcome.report_installation_outcome") as report, \
                patch("anaconda.cleanup_and_reboot"):
            anaconda.exitHandler()

        report.assert_called_once_with(
            InstallationStatus.FAILED, InstallationFailureReason.UNHANDLED_EXCEPTION
        )
        assert installation_outcome.reporting_started

    def test_exit_handler_skips_already_reported_outcome(self):
        """The exit handler does not report an outcome already reported."""
        installation_outcome.reporting_started = True

        with patch("pyanaconda.modules.common.constants.services.BOSS") as boss_cls, \
                patch("pyanaconda.installation_outcome.report_installation_outcome") as report, \
                patch("anaconda.cleanup_and_reboot"):
            anaconda.exitHandler()

        boss_cls.get_proxy.assert_not_called()
        report.assert_not_called()

    def test_exit_handler_always_cleans_up(self):
        """Cleanup still runs even if reading the outcome raises."""
        with patch("pyanaconda.modules.common.constants.services.BOSS") as boss_cls, \
                patch("anaconda.cleanup_and_reboot") as cleanup:
            boss_cls.get_proxy.side_effect = RuntimeError("no D-Bus connection")

            with pytest.raises(RuntimeError):
                anaconda.exitHandler()

        cleanup.assert_called_once()
