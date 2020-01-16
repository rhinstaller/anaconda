#
# Copyright (C) 2018 Red Hat, Inc.
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
import glob
import shutil
import json

from abc import ABCMeta

import pydbus

from pyanaconda.core import util
from pyanaconda.core.async_utils import async_action_nowait
from pyanaconda.core.signal import Signal
from pyanaconda.core.i18n import _

from pyanaconda.dbus.connection import Connection
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.interface import dbus_interface

from pyanaconda.modules.common.task import Task, TaskInterface
from pyanaconda.modules.common.constants.interfaces import SUBSCRIPTION_TASK
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.constants.objects import RHSM_ATTACH, RHSM_UNREGISTER, \
        RHSM_REGISTER_SERVER, RHSM_CONFIG
from pyanaconda.modules.common.errors.installation import SubscriptionTokenTransferError, \
        InsightsConnectError, InsightsClientMissingError
from pyanaconda.modules.common.errors import DBusError
from pyanaconda.modules.subscription import system_purpose

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def start_rhsm_private_bus():
    """Start the RHSM private DBus.

    The RHSM private DBus session is used for secure credential passing.

    NOTE: There is no locking involved, in starting/stopping of
          the private bus. So it's important to make sure only
          one task using the RHSM private bus is running at a time.
          Otherwise unexpected behavior might happen (one task shutting down
          private bus another task is still using, etc.).

    :return: address of the RHSM private DBus session
    :rtype: str
    """

    log.debug("RHSM: starting RHSM private DBus session")
    register_server_proxy = RHSM.get_proxy(RHSM_REGISTER_SERVER)
    locale = os.environ.get("LANG", "")
    private_bus_address = register_server_proxy.Start(locale)
    log.debug("RHSM: RHSM private DBus session started")
    return private_bus_address

def stop_rhsm_private_bus():
    """Stop the RHSM private DBus.

    The RHSM private DBus session is used for secure credential passing.

    We are only enabling the private bus for credential passing and
    shut it down once the credentials have been transferred.
    """

    log.debug("RHSM: shutting down the RHSM private DBus session")
    register_server_proxy = RHSM.get_proxy(RHSM_REGISTER_SERVER)
    locale = os.environ.get("LANG", "")
    register_server_proxy.Stop(locale)
    log.debug("RHSM: RHSM private DBus session has been shutdown")


class RHSMPrivateBusConnection(Connection):
    """Representation of a RHSM private bus connection."""

    def __init__(self, rhsm_private_bus_address):
        super().__init__()
        self._rhsm_private_bus_address = rhsm_private_bus_address

    def get_new_connection(self):
        """Connect to the RHSM private DBus session."""
        log.info("RHSM: Connecting to RHSM private DBus session")
        connection = pydbus.bus.Gio.DBusConnection.new_for_address_sync(self._rhsm_private_bus_address,
                                                                        pydbus.bus.Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT,
                                                                        None, None)
        log.info("RHSM: Connected to RHSM private DBus session")
        connection.pydbus.autoclose = False
        return connection.pydbus


class SystemPurposeConfigurationTask(Task):
    """Installation task for setting system purpose."""

    def __init__(self, sysroot, role, sla, usage, addons):
        """Create a new task.
        :param str sysroot: a path to the root of the installed system
        :param str role: System Purpose role
        :param str sla: System Purpose SLA
        :param str usage: System Purpose usage
        :param addons: list of System Purpose addons
        :type addons: list of str
        """
        super().__init__()
        self._sysroot = sysroot
        self._role = role
        self._sla = sla
        self._usage = usage
        self._addons = addons
        self.succeeded = Signal()

    @property
    def name(self):
        return "Set system purpose"

    def run(self):
        # apply System Purpose data
        system_purpose.give_the_system_purpose(
                self._sysroot,
                self._role,
                self._sla,
                self._usage,
                self._addons)
        # signal that we are done
        self._done()

    @async_action_nowait
    def _done(self):
        # tell anyone listening that we are done
        self.succeeded.emit()


# pylint: disable=abstract-method
class SubscriptionTask(Task, metaclass=ABCMeta):
    """A common base class for subcription related DBus tasks.

    It adds common fields used for passing error messages
    and status data from RHSM.
    """

    def __init__(self):
        super().__init__()
        self.error = ""
        # JSON data returned by the respective
        # RHSM DBus method (if any)
        self.subscription_json = ""

@dbus_interface(SUBSCRIPTION_TASK.interface_name)
class SubscriptionTaskInterface(TaskInterface):

    @property
    def Error(self) -> Str:
        """Contains description of an error."""
        return self.implementation.error


class RegisterWithUsernamePasswordTask(SubscriptionTask):
    """Register the system via username + password."""

    def __init__(self, username, password):
        """Create a new registration task.

        It is assumed the username and password have been
        validated before this task has been started.
        :param str username: Red Hat account username
        :param str password: Red Hat account password
        """
        super().__init__()
        self._username = username
        self._password = password

    @property
    def name(self):
        return "Register with Red Hat account username and password"

    def run(self):
        """Register the system with Red Hat account username and password."""
        log.debug("RHSM: connecting to RHSM private bus")
        private_bus_address = start_rhsm_private_bus()
        private_connection = RHSMPrivateBusConnection(private_bus_address)
        private_register_proxy = private_connection.get_proxy("com.redhat.RHSM1","/com/redhat/RHSM1/Register")
        log.debug("RHSM: registering with username and password")
        try:
            locale = os.environ.get("LANG", "")
            result = private_register_proxy.Register("", self._username, self._password, {}, {}, locale)
            self.subscription_json = result
            log.debug("RHSM: registered with username and password")
        except DBusError as e:
            log.debug("RHSM: failed to register with username and password: %s", str(e))
            # RHSM exception contain details as JSON due to DBus exception handling limitations
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message is missing
            message = exception_dict.get("message", _("Registration failed."))
            self.error = message
        finally:
            # registration done (one way or another), so shutdown the private bus used for
            # credential passing
            stop_rhsm_private_bus()


class RegisterWithOrganizationKeyTask(SubscriptionTask):
    """Register the system via organization and one or more activation keys."""

    def __init__(self, organization, activation_keys):
        """Create a new registration task.

        :param str organization: organization name for subscription purposes
        :param activation keys: activation keys
        :type activation_keys: list of str
        """
        super().__init__()
        self._organization = organization
        self._activation_keys = activation_keys

    @property
    def name(self):
        return "Register with organization name and activation key"

    def run(self):
        """Register the system with organization name and activation key."""
        log.debug("RHSM: connecting to RHSM private bus")
        private_bus_address = start_rhsm_private_bus()
        private_connection = RHSMPrivateBusConnection(private_bus_address)
        private_register_proxy = private_connection.get_proxy("com.redhat.RHSM1",
                                                              "/com/redhat/RHSM1/Register")
        log.debug("RHSM: registering with organization and activation key")
        try:
            locale = os.environ.get("LANG", "")
            result = private_register_proxy.RegisterWithActivationKeys(self._organization,
                                                                       self._activation_keys,
                                                                       {},
                                                                       {},
                                                                       locale)
            self.subscription_json = result
            log.debug("RHSM: registered with organization and activation key")
        except DBusError as e:
            log.debug("RHSM: failed to register with organization & key: %s", str(e))
            # RHSM exception contain details as JSON due to DBus exception handling limitations
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message is missing
            message = exception_dict.get("message", _("Registration failed."))
            self.error = message
        finally:
            # registration done (one way or another), so shutdown the private bus used for
            # credential passing
            stop_rhsm_private_bus()


class UnregisterTask(SubscriptionTask):
    """Unregister the system."""

    @property
    def name(self):
        return "Unregister the system"

    def run(self):
        """Unregister the system."""
        unregister_proxy = RHSM.get_proxy(RHSM_UNREGISTER)
        log.debug("RHSM: unregistering the system")
        try:
            locale = os.environ.get("LANG", "")
            result = unregister_proxy.Unregister({}, locale)
            self.subscription_json = result
            log.debug("RHSM: the system has been unregistered")
        except DBusError as e:
            log.exception("RHSM: failed to unregister: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Unregistration failed."))
            self.error = message


class AttachSubscriptionTask(SubscriptionTask):
    """Attach a subscription."""

    YUM_REPOS_PATH = "/etc/yum.repos.d"

    def __init__(self, sla):
        """Create a new task."""
        super().__init__()
        self._sla = sla

    @property
    def name(self):
        return "Attach a subscription"

    def run(self):
        """Attach a subscription to the installation environment.

        This subscription will be used to install the target system and then
        transferred to it via separate task.
        """
        log.debug("RHSM: creating yum.repos.d")
        log.debug("RHSM: auto-attaching a subscription")
        try:
            attach_proxy = RHSM.get_proxy(RHSM_ATTACH)
            locale = os.environ.get("LANG", "")
            result = attach_proxy.AutoAttach(self._sla, {}, locale)
            self.subscription_json = result
            log.debug("RHSM: auto-attached a subscription")
        except DBusError as e:
            log.debug("RHSM: auto-attach failed: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Failed to attach subscription."))
            self.error = message


class TransferSubscriptionTokensTask(Task):
    """Transfer subscription tokens to the target system."""

    RHSM_REPO_FILE_PATH = "/etc/yum.repos.d/redhat.repo"
    RHSM_CONFIG_FILE_PATH = "/etc/rhsm/rhsm.conf"
    RHSM_SYSPURPOSE_FILE_PATH = "/etc/rhsm/syspurpose/syspurpose.json"
    RHSM_ENTITLEMENT_KEYS_PATH = "/etc/pki/entitlement"
    RHSM_CONSUMER_KEY_PATH = "/etc/pki/consumer/key.pem"
    RHSM_CONSUMER_CERT_PATH = "/etc/pki/consumer/cert.pem"

    TARGET_REPO_FOLDER_PATH = "/etc/yum.repos.d"

    def __init__(self, sysroot, transfer_tokens):
        """Create a new task.

        :param str sysroot: target system root path
        :param bool transfer_tokens: if True attempt to transfer tokens to target system,
                                     if False do nothing
        """
        super().__init__()
        self._sysroot = sysroot
        self._transfer_tokens = transfer_tokens

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
        # create the output folder path if it does not exist
        if not os.path.isdir(output_folder):
            util.mkdirChain(output_folder)
        # transfer all the pem files in the input folder
        for pem_file_path in glob.glob(os.path.join(input_folder, "*.pem")):
            shutil.copy(pem_file_path, output_folder)
        # if we got this far the pem copy operation was a success
        return True

    def _copy_file_to_path(self, file_path, target_file_path):
        if not os.path.isfile(file_path):
            return False
        if not os.path.isdir(os.path.dirname(target_file_path)):
            util.mkdirChain(os.path.dirname(target_file_path))
        shutil.copy(file_path, target_file_path)
        return True

    def _transfer_system_purpose(self):
        # transfer the system purpose file if present
        # - this might be needed even if the system has not been subscribed
        #   during the installation and is therefore always attempted
        # - this means the syspurpose tool has been called in the installation
        #   environment & we need to transfer the results to the target system
        if os.path.exists(self.RHSM_SYSPURPOSE_FILE_PATH):
            log.debug("transfer-subscription-task: transferring syspurpose file")
            target_syspurpose_file_path = self._sysroot + self.RHSM_SYSPURPOSE_FILE_PATH
            self._copy_file_to_path(self.RHSM_SYSPURPOSE_FILE_PATH, target_syspurpose_file_path)

    def _transfer_rhsm_config_file(self):
        """Transfer the RHSM config file."""

        # Set RHSM log level back to INFO.
        # - we previously set the RHSM log level to DEBUG, which is also reflected in rhsm.conf
        # - this would mean RHSM would continue to log in debug mode also on the system once
        #   rhsm.conf has been copied over
        # - so set the log level back to INFO before we copy the config file
        # If RHSM get a way to only set the runtime log level in a non-persistent way,
        # we would be abale to eliminate this DBus call.
        log.debug("transfer-subscription-task: setting log level back to INFO")
        rhsm_config_proxy = RHSM.get_proxy(RHSM_CONFIG)
        rhsm_config_proxy.Set("logging.default_log_level", get_variant(Str, "INFO"), "")

        log.debug("transfer-subscription-task: transferring RHSM config file")
        target_rhsm_config_path = self._sysroot + self.RHSM_CONFIG_FILE_PATH
        if not self._copy_file_to_path(self.RHSM_CONFIG_FILE_PATH, target_rhsm_config_path):
            msg = "RHSM config file ({}) is missing.".format(self.RHSM_CONFIG_FILE_PATH)
            raise SubscriptionTokenTransferError(msg)

    def _tranfer_consumer_key(self):
        """Transfer the consumer key."""
        log.debug("transfer-subscription-task: transferring consumer key")
        target_consumer_key_path = self._sysroot + self.RHSM_CONSUMER_KEY_PATH
        if not self._copy_file_to_path(self.RHSM_CONSUMER_KEY_PATH, target_consumer_key_path):
            msg = "RHSM consumer key ({}) is missing.".format(self.RHSM_CONSUMER_KEY_PATH)
            raise SubscriptionTokenTransferError(msg)

    def _transfer_consumer_cert(self):
        """Transfer the consumer cert."""
        log.debug("transfer-subscription-task: transferring consumer certificate")
        target_consumer_key_path = self._sysroot + self.RHSM_CONSUMER_CERT_PATH
        if not self._copy_file_to_path(self.RHSM_CONSUMER_CERT_PATH, target_consumer_key_path):
            msg = "RHSM consumer certificate ({}) is missing.".format(self.RHSM_CONSUMER_CERT_PATH)
            raise SubscriptionTokenTransferError(msg)

    def _transfer_entitlement_certificates(self):
        """Transfer the entitlement certificates."""
        log.debug("transfer-subscription-task: transferring entitlement certificates")
        target_entitlement_keys_path = self._sysroot + self.RHSM_ENTITLEMENT_KEYS_PATH
        if not self._copy_pem_files(self.RHSM_ENTITLEMENT_KEYS_PATH, target_entitlement_keys_path):
            msg = "RHSM entitlement keys (from {}) are missing.".format(self.RHSM_ENTITLEMENT_KEYS_PATH)
            raise SubscriptionTokenTransferError(msg)

    def _transfer_repo_file(self):
        """Transfer the repo file."""
        log.debug("transfer-subscription-task: transferring repo file")
        target_repo_file_path = self._sysroot + self.RHSM_REPO_FILE_PATH
        if not self._copy_file_to_path(self.RHSM_REPO_FILE_PATH, target_repo_file_path):
            msg = "RHSM generated repo file ({}) is missing".format(self.RHSM_REPO_FILE_PATH)
            raise SubscriptionTokenTransferError(msg)

    def run(self):
        """Transfer the subscription tokens to the target system.

        Otherwise the target system would have to be registered and subscribed again.
        """
        self._transfer_system_purpose()

        # the other subscription tokens are only relevant if the system has been subscribed
        if not self._transfer_tokens:
            log.debug("transfer-subscription-task: transfer of subscription tokens not requested")
            return

        self._transfer_rhsm_config_file()
        self._tranfer_consumer_key()
        self._transfer_consumer_cert()
        self._transfer_entitlement_certificates()
        self._transfer_repo_file()


class ConnectToInsightsTask(Task):
    """Connect the target system to Red Hat Insights."""

    INSIGHTS_TOOL_PATH = "/usr/bin/insights-client"

    def __init__(self, sysroot, subscription_attached, connect_to_insights):
        """Create a new task.

        :param str sysroot: target system root path
        :param bool subscription_attached: if True then the system has been subscribed, False otherwise
        :param bool connect_to_insights: if True then connect the system to Insights, if False do nothing
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
            log.debug("insights-connect-task: Insights requested but target system is not subscribed, skipping")
            return

        # drop the leading / from INSIGHTS_TOOL_PATH to avoid issues with
        # os.path.join() due to two leading / in paths
        insights_path = os.path.join(self._sysroot, self.INSIGHTS_TOOL_PATH[1:])
        # check the insights client utility is available
        if not os.path.isfile(insights_path):
            raise InsightsClientMissingError("The insight-client tool ({}) is not available.".format(self.INSIGHTS_TOOL_PATH))

        # tell the insights client to connect to insights
        log.debug("insights-connect-task: connecting to insights")
        rc = util.execWithRedirect(self.INSIGHTS_TOOL_PATH, ["--register"], root=self._sysroot)
        if rc:
            raise InsightsConnectError("Connecting to Red Hat Insights failed.")
