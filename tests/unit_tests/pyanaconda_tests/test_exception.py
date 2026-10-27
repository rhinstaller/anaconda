# SPDX-License-Identifier: GPL-2.0-or-later

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from pyanaconda.core.constants import IPMI_FAILED
from pyanaconda.exception import AnacondaExceptionHandler
from pyanaconda.ui.lib.installation_progress_error import InstallationProgressErrorMixin


class ExceptionReportingTestCase:
    """Test reporting of local exceptions and failures already handled by Boss."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.handler = AnacondaExceptionHandler(Mock(), Mock(), Mock(), 1, Mock(), True)

    def test_task_failure_is_not_reported_again(self):
        spoke = InstallationProgressErrorMixin()
        failure = RuntimeError("installation task failed")
        spoke._task_proxy = Mock()
        spoke._task_proxy.Finish.side_effect = failure

        with pytest.raises(RuntimeError) as raised:
            spoke._finish_failed_installation()

        assert raised.value is failure
        dump_info = SimpleNamespace(exc_info=SimpleNamespace(value=raised.value))
        with patch("pyanaconda.exception.util.ipmi_report") as ipmi, \
                patch("pyanaconda.exception.util.run_kickstart_error_scripts") as scripts:
            self.handler._report_failure(dump_info)
            ipmi.assert_not_called()
            scripts.assert_not_called()

            # A subsequent, unrelated UI exception must still be reported.
            dump_info.exc_info.value = RuntimeError("UI failed")
            self.handler._report_failure(dump_info)

        scripts.assert_called_once_with(include_traceback=True)
        ipmi.assert_called_once_with(IPMI_FAILED)

    @pytest.mark.parametrize("script_error", [None, RuntimeError("diagnostic script failed")])
    def test_local_exception_keeps_original_reporting(self, script_error):
        dump_info = SimpleNamespace(exc_info=SimpleNamespace(value=RuntimeError("UI failed")))
        calls = Mock()
        calls.scripts.side_effect = script_error
        with patch("pyanaconda.exception.util.ipmi_report", calls.ipmi), \
                patch("pyanaconda.exception.util.run_kickstart_error_scripts", calls.scripts):
            self.handler._report_failure(dump_info)

        calls.scripts.assert_called_once_with(include_traceback=True)
        calls.ipmi.assert_called_once_with(IPMI_FAILED)
        assert calls.mock_calls[0][0] == "scripts"
