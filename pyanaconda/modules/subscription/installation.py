#
# Copyright (C) 2020 Red Hat, Inc.
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
import os

from dasbus.typing import get_variant, Str

from pyanaconda.core import util

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.errors.installation import InsightsConnectError, \
    InsightsClientMissingError

from pyanaconda.modules.subscription import system_purpose

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class ConnectToInsightsTask(Task):
    """Connect the target system to Red Hat Insights."""

    INSIGHTS_TOOL_PATH = "/usr/bin/insights-client"

    def __init__(self, sysroot, subscription_attached, connect_to_insights):
        """Create a new task.

        :param str sysroot: target system root path
        :param bool subscription_attached: if True then the system has been subscribed,
                                           False otherwise
        :param bool connect_to_insights: if True then connect the system to Insights,
                                         if False do nothing
        """
        super().__init__()
        self._sysroot = sysroot
        self._subscription_attached = subscription_attached
        self._connect_to_insights = connect_to_insights

    @property
    def name(self):
        return "Connect the target system to Red Hat Insights"

    def run(self):
        """Connect the target system to Red Hat Insights."""
        # check if we should connect to Red Hat Insights
        if not self._connect_to_insights:
            log.debug("insights-connect-task: Insights not requested, skipping")
            return
        elif not self._subscription_attached:
            log.debug("insights-connect-task: "
                      "Insights requested but target system is not subscribed, skipping")
            return

        insights_path = util.join_paths(self._sysroot, self.INSIGHTS_TOOL_PATH)
        # check the insights client utility is available
        if not os.path.isfile(insights_path):
            raise InsightsClientMissingError(
                "The insight-client tool ({}) is not available.".format(self.INSIGHTS_TOOL_PATH)
            )

        # tell the insights client to connect to insights
        log.debug("insights-connect-task: connecting to insights")
        rc = util.execWithRedirect(self.INSIGHTS_TOOL_PATH, ["--register"], root=self._sysroot)
        if rc:
            raise InsightsConnectError("Connecting to Red Hat Insights failed.")


class SystemPurposeConfigurationTask(Task):
    """Installation task for setting system purpose."""

    def __init__(self, sysroot, system_purpose_data):
        """Create a new system purpose configuration task.

        :param str sysroot: a path to the root of the installed system
        :param system_purpose_data: system purpose data DBus structure
        :type system_purpose_data: DBusData instance
        """
        super().__init__()
        self._sysroot = sysroot
        self._system_purpose_data = system_purpose_data

    @property
    def name(self):
        return "Set system purpose"

    def run(self):
        # apply System Purpose data
        return system_purpose.give_the_system_purpose(
            sysroot=self._sysroot,
            role=self._system_purpose_data.role,
            sla=self._system_purpose_data.sla,
            usage=self._system_purpose_data.usage,
            addons=self._system_purpose_data.addons
        )


class RestoreRHSMLogLevelTask(Task):
    """Restore RHSM log level back to INFO."""

    def __init__(self, rhsm_config_proxy):
        """Create a new task.
        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy

    @property
    def name(self):
        return "Restoring subscription manager log level"

    def run(self):
        """Set RHSM log level back to INFO.

        We previously set the RHSM log level to DEBUG, which is also
        reflected in rhsm.conf. This would mean RHSM would continue to
        log in debug mode also on the system once rhsm.conf has been
        copied over to the target system.

        So set the log level back to INFO before we copy the config file.
        """
        log.debug("subscription: setting RHSM log level back to INFO")
        self._rhsm_config_proxy.Set("logging.default_log_level",
                                    get_variant(Str, "INFO"), "")
