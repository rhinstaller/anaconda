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
import glob
import os
import shutil

from dasbus.typing import Str, get_variant

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.constants import RHSM_SYSPURPOSE_FILE_PATH
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.core.subscription import check_system_purpose_set
from pyanaconda.modules.common.errors.installation import (
    InsightsClientMissingError,
    InsightsConnectError,
    SubscriptionTokenTransferError,
)
from pyanaconda.modules.common.errors.subscription import SatelliteProvisioningError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.subscription import satellite

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

        insights_path = join_paths(self._sysroot, self.INSIGHTS_TOOL_PATH)
        # check the insights client utility is available
        if not os.path.isfile(insights_path):
            raise InsightsClientMissingError(
                "The insight-client tool ({}) is not available.".format(self.INSIGHTS_TOOL_PATH)
            )

        # tell the insights client to connect to insights
        log.debug("insights-connect-task: connecting to insights")
        rc = util.execWithRedirect(self.INSIGHTS_TOOL_PATH, ["--register"], root=self._sysroot)
        if rc:
            raise InsightsConnectError("Failed to connect to Red Hat Insights.")


class RestoreRHSMDefaultsTask(Task):
    """Restore RHSM defaults we changed for install time purposes.

    At the moment this means setting the RHSM log level back to INFO
    from DEBUG and making sure SSL certificate validation is enabled
    (as we might turn it off for the installation run if requested by
     the user).
    """

    def __init__(self, rhsm_config_proxy):
        """Create a new task.
        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy

    @property
    def name(self):
        return "Restoring subscription manager defaults"

    def run(self):
        """Restore RHSM defaults we changed.

        We previously set the RHSM log level to DEBUG, which is also
        reflected in rhsm.conf. This would mean RHSM would continue to
        log in debug mode also on the system once rhsm.conf has been
        copied over to the target system.

        The same thing needs to be done for the server.insecure key
        that we migh set to "1" previously on user request.

        So set the log level back to INFO before we copy the config file
        and make sure server.insecure is equal to "0".
        """
        log.debug("subscription: setting RHSM log level back to INFO")
        log.debug("subscription: making sure RHSM SSL certificate validation is enabled")
        config_dict = {
            "logging.default_log_level": get_variant(Str, "INFO"),
            "server.insecure": get_variant(Str, "0")
        }

        # set all the values at once atomically
        self._rhsm_config_proxy.SetAll(config_dict, "")


class TransferSubscriptionTokensTask(Task):
    """Transfer subscription tokens to the target system."""

    RHSM_REPO_FILE_PATH = "/etc/yum.repos.d/redhat.repo"
    RHSM_CONFIG_FILE_PATH = "/etc/rhsm/rhsm.conf"
    RHSM_ENTITLEMENT_KEYS_PATH = "/etc/pki/entitlement"
    RHSM_CONSUMER_KEY_PATH = "/etc/pki/consumer/key.pem"
    RHSM_CONSUMER_CERT_PATH = "/etc/pki/consumer/cert.pem"

    def __init__(self, sysroot, transfer_subscription_tokens):
        """Create a new task.

        :param str sysroot: target system root path
        :param bool transfer_subscription_tokens: if True attempt to transfer subscription
                                                  tokens to target system (we always transfer
                                                  system purpose data unconditionally)
        """
        super().__init__()
        self._sysroot = sysroot
        self._transfer_subscription_tokens = transfer_subscription_tokens

    @property
    def name(self):
        return "Transfer subscription tokens to target system"

    def _copy_pem_files(self, input_folder, output_folder, not_empty=True):
        """Copy all pem files from input_folder to output_folder.

        Files with the pem extension are generally encryption keys and certificates.
        If output_folder does not exist, it & any parts of its path will
        be created.

        :param str input_folder: input folder for the pem files
        :param str output_folder: output folder where to copy the pem files
        :return: False if the input directory does not exists or is empty,
                 True after all pem files have be successfully copied
        :rtype: bool
        """
        # check the input folder exists
        if not os.path.isdir(input_folder):
            return False
        # optionally check the input folder is not empty
        if not_empty and not os.listdir(input_folder):
            return False
        # make sure the output folder exist
        make_directories(output_folder)
        # transfer all the pem files in the input folder
        for pem_file_path in glob.glob(os.path.join(input_folder, "*.pem")):
            shutil.copy(pem_file_path, output_folder)
        # if we got this far the pem copy operation was a success
        return True

    def _copy_file(self, file_path, target_file_path):
        if not os.path.isfile(file_path):
            return False
        # make sure the output folder exists
        make_directories(os.path.dirname(target_file_path))
        shutil.copy(file_path, target_file_path)
        return True

    def _transfer_file(self, target_path, target_name):
        """Transfer a file with nice logs and raise an exception if it does not exist."""
        log.debug("subscription: transferring %s", target_name)
        target_repo_file_path = join_paths(self._sysroot, target_path)
        if not self._copy_file(target_path, target_repo_file_path):
            msg = "{} ({}) is missing".format(target_name, self.RHSM_REPO_FILE_PATH)
            raise SubscriptionTokenTransferError(msg)

    def _transfer_system_purpose(self):
        """Transfer the system purpose file if present.

        A couple notes:
         - this might be needed even if the system has not been subscribed
           during the installation and is therefore always attempted
         - this means the syspurpose tool has been called in the installation
           environment & we need to transfer the results to the target system
        """
        if check_system_purpose_set(sysroot="/"):
            log.debug("subscription: transferring syspurpose file")
            target_syspurpose_file_path = self._sysroot + RHSM_SYSPURPOSE_FILE_PATH
            self._copy_file(RHSM_SYSPURPOSE_FILE_PATH, target_syspurpose_file_path)

    def _transfer_entitlement_keys(self):
        """Transfer the entitlement keys."""
        log.debug("subscription: transferring entitlement keys")
        target_entitlement_keys_path = self._sysroot + self.RHSM_ENTITLEMENT_KEYS_PATH
        if not self._copy_pem_files(self.RHSM_ENTITLEMENT_KEYS_PATH, target_entitlement_keys_path):
            msg = "RHSM entitlement keys (from {}) are missing.".format(
                self.RHSM_ENTITLEMENT_KEYS_PATH)
            raise SubscriptionTokenTransferError(msg)

    def run(self):
        """Transfer the subscription tokens to the target system.

        Otherwise the target system would have to be registered and subscribed again
        due to missing subscription tokens.
        """
        self._transfer_system_purpose()

        # the other subscription tokens are only relevant if the system has been subscribed
        if not self._transfer_subscription_tokens:
            log.debug("subscription: transfer of subscription tokens not requested")
            return

        # transfer entitlement keys
        self._transfer_entitlement_keys()

        # transfer the consumer key
        self._transfer_file(self.RHSM_CONSUMER_KEY_PATH, "RHSM consumer key")

        # transfer the consumer cert
        self._transfer_file(self.RHSM_CONSUMER_CERT_PATH, "RHSM consumer cert")

        # transfer the redhat.repo file
        self._transfer_file(self.RHSM_REPO_FILE_PATH, "RHSM repo file")

        # transfer the RHSM config file
        self._transfer_file(self.RHSM_CONFIG_FILE_PATH, "RHSM config file")


class ProvisionTargetSystemForSatelliteTask(Task):
    """Provision target system for communication with Satellite.

    If the System gets registered to Satellite at installation time,
    the provisioning is applied only to the installation environment.
    This task makes sure it is applied also on the target system.

    Run the appropriate Satellite provisioning script on the target system.

    This should assure the target system has all the needed certificates
    installed and rhsm.conf tweaks applied.
    """

    def __init__(self, provisioning_script):
        """Create a new task.

        :param str provisioning_script: Satellite provisioning script in string form
        """
        super().__init__()
        self._provisioning_script = provisioning_script

    @property
    def name(self):
        return "Provisioning target system for Satellite"

    def run(self):
        """Provision target system for Satellite.

        First check if we are actually registered to a Satellite instance
        by checking if we got a provisioning script.

        If not, do nothing.

        If we are registered to a Satellite instance, run the Satellite
        provisioning script that has been downloaded from the instance previously.

        """
        if self._provisioning_script:
            log.debug("subscription: provisioning target system for Satellite")
            provisioning_success = satellite.run_satellite_provisioning_script(
                provisioning_script=self._provisioning_script,
                run_on_target_system=True

            )
            if provisioning_success:
                log.debug("subscription: target system successfully provisioned for Satellite")
            else:
                raise SatelliteProvisioningError("Satellite provisioning script failed.")
        else:
            # lets assume here that no provisioning script == not registered to Satellite
            log.debug(
                "subscription: not registered to Satellite, skipping Satellite provisioning."
            )
