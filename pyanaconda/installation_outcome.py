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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.constants import IPMI_ABORTED, IPMI_FAILED, IPMI_FINISHED
from pyanaconda.modules.common.constants.installation import (
    InstallationFailureReason,
    InstallationStatus,
)

log = get_module_logger(__name__)

__all__ = ["installation_outcome", "report_installation_outcome"]

TERMINAL_STATUSES = (
    InstallationStatus.SUCCEEDED,
    InstallationStatus.FAILED,
    InstallationStatus.ABORTED,
)


def report_installation_outcome(status, failure_reason):
    """Report a terminal installation outcome via IPMI and kickstart scripts.

    Sends the IPMI event matching the outcome and runs the %onerror (and,
    for an unhandled exception, also the %traceback) kickstart scripts.

    The calls can block for a while, so this must never run on the D-Bus
    event loop of a service that is expected to stay responsive. Call it
    either from the main process once the outcome is known, or during
    shutdown.

    :param status: a terminal InstallationStatus value
    :param failure_reason: an InstallationFailureReason value
    """
    if status == InstallationStatus.SUCCEEDED:
        util.ipmi_report(IPMI_FINISHED)
    elif status == InstallationStatus.ABORTED:
        util.ipmi_report(IPMI_ABORTED)
        util.run_kickstart_error_scripts(include_traceback=False)
    elif status == InstallationStatus.FAILED:
        if failure_reason == InstallationFailureReason.INSTALLATION_ERROR:
            util.ipmi_report(IPMI_ABORTED)
            util.run_kickstart_error_scripts(include_traceback=False)
        else:
            util.ipmi_report(IPMI_FAILED)
            util.run_kickstart_error_scripts(include_traceback=True)
    else:
        log.warning("Unexpected terminal installation status: %s", status)


class InstallationOutcomeReporter:
    """Report a terminal installation outcome exactly once, from the main process.

    Boss only records the installation outcome; this reporter performs the
    (possibly slow, best-effort) IPMI and kickstart script reporting, once,
    from whichever part of the main process first learns the outcome: the
    GUI/TUI progress spoke on success, the exception handler on a fatal
    exception, or the process exit handler as a fallback for anything else
    (notably WebUI, which has no outcome-reporting logic of its own).
    """

    def __init__(self):
        self.reporting_started = False

    def mark_reporting_started(self):
        """Record that the reporting has already been handled elsewhere."""
        self.reporting_started = True

    def report(self, status, failure_reason):
        """Report the outcome, unless it was already reported.

        :param status: a terminal InstallationStatus value
        :param failure_reason: an InstallationFailureReason value
        """
        if self.reporting_started:
            return
        if status not in TERMINAL_STATUSES:
            return
        self.reporting_started = True
        report_installation_outcome(status, failure_reason)


installation_outcome = InstallationOutcomeReporter()
