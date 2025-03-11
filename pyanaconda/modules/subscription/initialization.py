#
# Kickstart module for subscription handling.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import os
import sys

from dasbus.typing import Str, get_variant

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import RHSM_SERVICE_TIMEOUT
from pyanaconda.core.service import is_service_installed, start_service
from pyanaconda.core.threads import thread_manager
from pyanaconda.modules.common.constants.objects import RHSM_CONFIG
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.errors.task import NoResultError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.subscription.constants import RHSM_SERVICE_NAME

log = get_module_logger(__name__)


def check_initial_conditions():
    """Can the Subscription service run?"""

    # Exclude the dir and image installations.
    if not conf.target.is_hardware:
        log.debug(
            "subscription: Unsupported type of the installation target. "
            "The Subscription module won't be started."
        )
        sys.exit(1)

    # Exclude environments without the rhsm service.
    if not is_service_installed(RHSM_SERVICE_NAME):
        log.debug(
            "subscription: The required rhsm systemd service is not available. "
            "The Subscription module won't be started."
        )
        sys.exit(1)


class StartRHSMTask(Task):
    """Task for starting the RHSM DBus service."""

    def __init__(self, verify_ssl=True):
        """Create a new task for starting the RHSM DBus service.

        :param bool verify_ssl: True if RHSM should be configured to verify SSL certificates,
                                False if RHSM should be set to *not* verify SSL certificates

        NOTE: If RHSM SSL verification is disabled, this is install time only, as we will
              always turn it back on unconditionally at the same time we roll back the RHSM
              log level change.
        """
        super().__init__()
        self._verify_ssl = verify_ssl

    @property
    def name(self):
        return "Start RHSM DBus service"

    def run(self):
        """Start the RHSM DBus service.

        And also some related tasks, such as setting RHSM log levels.
        """
        # Due to a RHSM bug (https://bugzilla.redhat.com/show_bug.cgi?id=1700441)
        # we need to create /etc/yum.repos.d if it does not exist. Otherwise RHSM
        # will not create the expected redhat.repo file inside it.
        if not os.path.exists("/etc/yum.repos.d"):
            log.debug("subscription: creating /etc/yum.repos.d")
            os.mkdir("/etc/yum.repos.d")

        # start the rhsm.service
        # - this is blocking, but as we are effectively running in a thread
        # it should not be an issue
        # - if the return code is non-zero, return False immediately
        rc = start_service(RHSM_SERVICE_NAME)
        if rc:
            log.warning(
                "subscription: RHSM systemd service failed to start with error code: %s",
                rc
            )
            return False

        # create a temporary proxy to set the log levels
        rhsm_config_proxy = RHSM.get_proxy(RHSM_CONFIG, interface_name=RHSM_CONFIG)

        # set RHSM log levels to debug
        # - otherwise the RHSM log output is not usable for debugging subscription issues
        log.debug("subscription: setting RHSM log level to DEBUG")
        config_dict = {"logging.default_log_level": get_variant(Str, "DEBUG")}
        # turn OFF SSL certificate validation (if requested)
        if not self._verify_ssl:
            log.debug("subscription: disabling RHSM SSL certificate validation")
            config_dict["server.insecure"] = get_variant(Str, "1")

        # set all the values at once atomically
        rhsm_config_proxy.SetAll(config_dict, "")

        # all seems fine
        log.debug("subscription: RHSM service start successfully.")
        return True

    def is_service_available(self, timeout=RHSM_SERVICE_TIMEOUT):
        """Return if RHSM service is available or wait if startup is ongoing."""
        if self.is_running:
            # Wait up to defined timeout for the service to startup
            # by joining the thread running the task. We specify a timeout when
            # joining to prevent a deadlocked task blocking this method forever.
            thread = thread_manager.get(self._thread_name)
            if thread:
                log.debug("subscription: waiting for RHSM service to start for up to %f seconds.",
                          timeout)
                thread.join(timeout)
            else:
                log.error("subscription: RHSM startup task is running but no thread found.")
                return False

        # now check again if the task is still running
        if self.is_running:
            # looks like we timed out
            log.debug("subscription: RHSM service not available after waiting for %f seconds.",
                      timeout)
            return False
        else:
            # If we got this far, the task has finished running. If the result is True
            # it was able to successfully start the systemd unit and connect to the DBus API.
            # If the result is False, then the service failed to start.
            try:
                result = self.get_result()
            except NoResultError:
                # if the task fails in weird ways, there could apparently be no result
                log.error("subscription: got no result from StartRHSMTask")
                result = False
            return result
