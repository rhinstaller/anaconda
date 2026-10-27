# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import Mock, patch

import pytest

from pyanaconda.core.constants import IPMI_ABORTED, IPMI_FAILED, IPMI_FINISHED
from pyanaconda.modules.boss.installation import report_installation_outcome
from pyanaconda.modules.common.constants.installation import (
    InstallationFailureReason,
    InstallationStatus,
)


class InstallationOutcomeTestCase:

    @pytest.mark.parametrize("status, reason, event, traceback", [
        (InstallationStatus.SUCCEEDED, InstallationFailureReason.NONE, IPMI_FINISHED, None),
        (InstallationStatus.ABORTED, InstallationFailureReason.NONE, IPMI_ABORTED, False),
        (InstallationStatus.FAILED, InstallationFailureReason.INSTALLATION_ERROR, IPMI_ABORTED, False),
        (InstallationStatus.FAILED, InstallationFailureReason.UNHANDLED_EXCEPTION, IPMI_FAILED, True),
    ])
    def test_reports_matching_event_and_scripts(self, status, reason, event, traceback):
        calls = Mock()
        with patch("pyanaconda.modules.boss.installation.util.ipmi_report", calls.ipmi), \
                patch("pyanaconda.modules.boss.installation.util.run_kickstart_error_scripts", calls.scripts):
            report_installation_outcome(status, reason)

        calls.ipmi.assert_called_once_with(event)
        if traceback is None:
            calls.scripts.assert_not_called()
        else:
            calls.scripts.assert_called_once_with(include_traceback=traceback)
            assert calls.mock_calls[0][0] == "ipmi"
