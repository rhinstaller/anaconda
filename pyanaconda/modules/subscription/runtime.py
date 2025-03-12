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
import json
import os
from collections import namedtuple

import gi
from dasbus.connection import MessageBus
from dasbus.error import DBusError
from dasbus.typing import Bool, Str, get_native, get_variant

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import service
from pyanaconda.core.constants import (
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD,
)
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import ProxyString
from pyanaconda.modules.common.constants.objects import (
    RHSM_CONFIG,
    RHSM_REGISTER,
    RHSM_REGISTER_SERVER,
    RHSM_SYSPURPOSE,
    RHSM_UNREGISTER,
)
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.errors.subscription import (
    MultipleOrganizationsError,
    RegistrationError,
    SatelliteProvisioningError,
    UnregistrationError,
)
from pyanaconda.modules.common.structures.subscription import (
    OrganizationData,
    SystemPurposeData,
)
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.subscription import satellite, system_purpose
from pyanaconda.modules.subscription.constants import (
    RHSM_SERVICE_NAME,
    SERVER_HOSTNAME_NOT_SATELLITE_PREFIX,
)
from pyanaconda.modules.subscription.subscription_interface import (
    RetrieveOrganizationsTaskInterface,
)
from pyanaconda.modules.subscription.utils import flatten_rhsm_nested_dict
from pyanaconda.ui.lib.subscription import (
    org_keys_sufficient,
    username_password_sufficient,
)

gi.require_version("Gio", "2.0")
from gi.repository import Gio

log = get_module_logger(__name__)


class RHSMPrivateBus(MessageBus):
    """Representation of RHSM private bus connection that can be used as a context manager."""

    def __init__(self, rhsm_register_server_proxy, *args, **kwargs):
        """Representation of RHSM private bus connection that can be used as a context manager.

        :param rhsm_register_server_proxy: DBus proxy for the RHSM RegisterServer object
        """
        super().__init__(*args, **kwargs)
        self._rhsm_register_server_proxy = rhsm_register_server_proxy
        self._private_bus_address = None

    def __enter__(self):
        log.debug("subscription: starting RHSM private DBus session")
        locale = os.environ.get("LANG", "")
        self._private_bus_address = self._rhsm_register_server_proxy.Start(locale)
        log.debug("subscription: RHSM private DBus session has been started")
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_traceback):
        log.debug("subscription: shutting down the RHSM private DBus session")
        self.disconnect()
        locale = os.environ.get("LANG", "")
        self._rhsm_register_server_proxy.Stop(locale)
        log.debug("subscription: RHSM private DBus session has been shutdown")

    def _get_connection(self):
        """Get a connection to RHSM private DBus session."""
        # the RHSM private bus address is potentially sensitive
        # so we will not log it
        log.info("Connecting to the RHSM private DBus session.")
        return self._provider.get_addressed_bus_connection(
            bus_address=self._private_bus_address,
            flags=Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        )


SystemSubscriptionData = namedtuple("SystemSubscriptionData",
                                    ["system_purpose_data"])


class SystemPurposeConfigurationTask(Task):
    """Runtime task for setting system purpose."""

    def __init__(self, rhsm_syspurpose_proxy, system_purpose_data):
        """Create a new system purpose configuration task.

        :param rhsm_syspurpose_proxy: DBus proxy for the RHSM Syspurpose object
        :param system_purpose_data: system purpose data DBus structure
        :type system_purpose_data: DBusData instance
        """
        super().__init__()
        self._rhsm_syspurpose_proxy = rhsm_syspurpose_proxy
        self._system_purpose_data = system_purpose_data

    @property
    def name(self):
        return "Set system purpose"

    def run(self):
        # the task is always expected to run in the installation environment
        # - if existing data is present, it will be cleared and then
        #   replaced by new data
        return system_purpose.give_the_system_purpose(
            sysroot="/",
            rhsm_syspurpose_proxy=self._rhsm_syspurpose_proxy,
            role=self._system_purpose_data.role,
            sla=self._system_purpose_data.sla,
            usage=self._system_purpose_data.usage,
            addons=self._system_purpose_data.addons
        )


class SetRHSMConfigurationTask(Task):
    """Task for setting configuration to the RHSM service.

    Set configuration options of the RHSM service via it's
    DBus interface, based on the provided SubscriptionRequest
    structure.

    Also in case one of the configuration options was unset,
    restore the key to its original value. This way for example
    a user decides at runtime to use the default server hostname
    or RHSM baseurl, they can just delete the value in the UI,
    triggering the original value to be restored when we encounter
    the empty value for a key that originally was set to
    a non empty value.
    """

    # Keys in the RHSM config key/value store we care about and
    # should be able to restore to original value.
    #
    # NOTE: These keys map 1:1 to rhsm.conf. To see what they do the
    #       best bet is to check the /etc/rhsm/rhsm.conf file on a system
    #       with the subscription-manager package installed. The file
    #       is heavily documented with comment's explaining what
    #       the different keys do.
    CONFIG_KEY_SERVER_HOSTNAME = "server.hostname"
    CONFIG_KEY_SERVER_PROXY_HOSTNAME = "server.proxy_hostname"
    CONFIG_KEY_SERVER_PROXY_PORT = "server.proxy_port"
    CONFIG_KEY_SERVER_PROXY_USER = "server.proxy_user"
    CONFIG_KEY_SERVER_PROXY_PASSWORD = "server.proxy_password"
    CONFIG_KEY_RHSM_BASEURL = "rhsm.baseurl"

    def __init__(self, rhsm_config_proxy, rhsm_config_defaults, subscription_request):
        """Create a new task for setting RHSM configuration.

        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        :param dict rhsm_config_defaults: a dictionary of original RHSM configuration values
        :param subscription_request: subscription request DBus Structure
        :type subscription_request: SubscriptionRequest instance
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy
        self._request = subscription_request
        self._rhsm_config_defaults = rhsm_config_defaults

    @property
    def name(self):
        return "Set RHSM configuration."

    def run(self):
        log.debug("subscription: setting RHSM config values")
        # We will use the SetAll() dbus method and we need to
        # assemble a dictionary that we will feed to it.
        # Start by preparing a SubscriptionData property mapping
        # to the RHSM config keys.
        #
        # A note about constructing the dict:
        # - DBus API needs all values to be strings, so we need to convert the
        #   port number to string
        # - all values need to be string variants
        # - proxy password is stored in SecretData instance and we need to retrieve
        #   its value
        # - server host name might have a prefix indicating the given URL is not
        #   a Satellite URL, drop that prefix before setting the value to RHSM

        # drop the not-satellite prefix, if any
        server_hostname = self._request.server_hostname.removeprefix(
            SERVER_HOSTNAME_NOT_SATELLITE_PREFIX
        )
        property_key_map = {
            self.CONFIG_KEY_SERVER_HOSTNAME: server_hostname,
            self.CONFIG_KEY_SERVER_PROXY_HOSTNAME: self._request.server_proxy_hostname,
            self.CONFIG_KEY_SERVER_PROXY_PORT: str(self._request.server_proxy_port),
            self.CONFIG_KEY_SERVER_PROXY_USER: self._request.server_proxy_user,
            self.CONFIG_KEY_SERVER_PROXY_PASSWORD: self._request.server_proxy_password.value,
            self.CONFIG_KEY_RHSM_BASEURL: self._request.rhsm_baseurl
        }

        # Then process the mapping into the final dict we will set to RHSM. This includes
        # checking if some values have been cleared by the user and should be restored to
        # the original values that have been in the RHSM config before we started
        # manipulating it.
        #
        # Also the RHSM DBus API requires a dict of variants, so we need to provide
        # that as well.
        config_dict = {}
        for key, value in property_key_map.items():
            if value:
                # if value is present in request, use it
                config_dict[key] = get_variant(Str, value)
            else:
                # if no value is present in request, use
                # value from the original RHSM config state
                # (if any)
                log.debug("subscription: restoring original value for RHSM config key %s", key)
                config_dict[key] = get_variant(Str, self._rhsm_config_defaults.get(key, ""))

        # and finally set the dict to RHSM via the DBus API
        self._rhsm_config_proxy.SetAll(config_dict, "")


class RegisterWithUsernamePasswordTask(Task):
    """Register the system via username + password."""

    def __init__(self, rhsm_register_server_proxy, username, password, organization):
        """Create a new registration task.

        It is assumed the username and password have been
        validated before this task has been started.

        :param rhsm_register_server_proxy: DBus proxy for the RHSM RegisterServer object
        :param str username: Red Hat account username
        :param str password: Red Hat account password
        :param str organization: organization id
        """
        super().__init__()
        self._rhsm_register_server_proxy = rhsm_register_server_proxy
        self._username = username
        self._password = password
        self._organization = organization

    @property
    def name(self):
        return "Register with Red Hat account username and password"

    def run(self):
        """Register the system with Red Hat account username and password.

        :raises: RegistrationError if calling the RHSM DBus API returns an error
        :return: JSON string describing registration state
        :rtype: str
        """
        if not self._organization:
            # If no organization id is specified check if the account is member of more than
            # one organization.
            # If it is member of just one organization, this is fine and we can proceed
            # with the registration attempt.
            # If it is member of 2 or more organizations, this is an invalid state as without
            # an organization id being specified RHSM will not know what organization to register
            # the machine. In this throw raise a specific exception so that the GUI can react
            # accordingly and help the user fix the issue.

            org_data_task = RetrieveOrganizationsTask(
                rhsm_register_server_proxy=self._rhsm_register_server_proxy,
                username=self._username,
                password=self._password,
                reset_cache=True
            )
            org_list = org_data_task.run()
            if len(org_list) > 1:
                raise MultipleOrganizationsError(
                    _("Please select an organization for your account and try again.")
                )

        log.debug("subscription: registering with username and password")
        with RHSMPrivateBus(self._rhsm_register_server_proxy) as private_bus:
            try:
                locale = os.environ.get("LANG", "")

                private_register_proxy = private_bus.get_proxy(RHSM.service_name,
                                                               RHSM_REGISTER.object_path)
                registration_data = private_register_proxy.Register(
                    self._organization,
                    self._username,
                    self._password,
                    {"enable_content": get_variant(Bool, True)},
                    {},
                    locale
                )
                log.debug("subscription: registered with username and password")
                return registration_data
            except DBusError as e:
                log.debug("subscription: failed to register with username and password: %s",
                          str(e))
                # RHSM exception contain details as JSON due to DBus exception handling limitations
                exception_dict = json.loads(str(e))
                # return a generic error message in case the RHSM provided error message is missing
                message = exception_dict.get("message", _("Registration failed."))
                raise RegistrationError(message) from None


class RegisterWithOrganizationKeyTask(Task):
    """Register the system via organization and one or more activation keys."""

    def __init__(self, rhsm_register_server_proxy, organization, activation_keys):
        """Create a new registration task.

        :param rhsm_register_server_proxy: DBus proxy for the RHSM RegisterServer object
        :param str organization: organization name for subscription purposes
        :param activation keys: activation keys
        :type activation_keys: list of str
        """
        super().__init__()
        self._rhsm_register_server_proxy = rhsm_register_server_proxy
        self._organization = organization
        self._activation_keys = activation_keys

    @property
    def name(self):
        return "Register with organization name and activation key"

    def run(self):
        """Register the system with organization name and activation key.

        :raises: RegistrationError if calling the RHSM DBus API returns an error
        :return: JSON string describing registration state
        :rtype: str
        """
        log.debug("subscription: registering with organization and activation key")
        with RHSMPrivateBus(self._rhsm_register_server_proxy) as private_bus:
            try:
                locale = os.environ.get("LANG", "")
                private_register_proxy = private_bus.get_proxy(RHSM.service_name,
                                                               RHSM_REGISTER.object_path)
                registration_data = private_register_proxy.RegisterWithActivationKeys(
                    self._organization,
                    self._activation_keys,
                    {},
                    {},
                    locale
                )
                log.debug("subscription: registered with organization and activation key")
                return registration_data
            except DBusError as e:
                log.debug("subscription: failed to register with organization & key: %s", str(e))
                # RHSM exception contain details as JSON due to DBus exception handling limitations
                exception_dict = json.loads(str(e))
                # return a generic error message in case the RHSM provided error message is missing
                message = exception_dict.get("message", _("Registration failed."))
                raise RegistrationError(message) from None


class UnregisterTask(Task):
    """Unregister the system."""

    def __init__(self, rhsm_observer, registered_to_satellite, rhsm_configuration):
        """Create a new unregistration task.

        :param rhsm_observer: DBus service observer for talking to RHSM
        :param dict rhsm_configuration: flat "clean" RHSM configuration dict to restore
        :param bool registered_to_satellite: were we registered to Satellite ?
        """
        super().__init__()
        self._rhsm_observer = rhsm_observer
        self._registered_to_satellite = registered_to_satellite
        self._rhsm_configuration = rhsm_configuration

    @property
    def name(self):
        return "Unregister the system"

    def run(self):
        """Unregister the system."""
        log.debug("registration attempt: unregistering the system")
        try:
            locale = os.environ.get("LANG", "")
            rhsm_unregister_proxy = self._rhsm_observer.get_proxy(RHSM_UNREGISTER)
            rhsm_unregister_proxy.Unregister({}, locale)
            log.debug("subscription: the system has been unregistered")
        except DBusError as e:
            log.error("registration attempt: failed to unregister: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Unregistration failed."))
            raise UnregistrationError(message) from e

        # in case we were Registered to Satellite, roll back Satellite provisioning as well
        if self._registered_to_satellite:
            log.debug("registration attempt: rolling back Satellite provisioning")
            rollback_task = RollBackSatelliteProvisioningTask(
                rhsm_config_proxy=self._rhsm_observer.get_proxy(RHSM_CONFIG),
                rhsm_configuration=self._rhsm_configuration
            )
            rollback_task.run()
            log.debug("registration attempt: Satellite provisioning rolled back")


class ParseSubscriptionDataTask(Task):
    """Parse data about subscriptions attached to the installation environment."""

    def __init__(self, rhsm_syspurpose_proxy):
        """Create a new attached subscriptions parsing task.

        :param rhsm_syspurpose_proxy: DBus proxy for the RHSM Syspurpose object
        """
        super().__init__()
        self._rhsm_syspurpose_proxy = rhsm_syspurpose_proxy

    @property
    def name(self):
        return "Parse attached subscription data"

    @staticmethod
    def _parse_system_purpose_json(final_syspurpose_json):
        """Parse the JSON into a SystemPurposeData instance.

        The expected JSON is a simple three key dictionary listing the final
        System Purpose state after subscription/subscriptions have been attached.

        :param str final_syspurpose_json: JSON describing final syspurpose state
        :return: final system purpose data
        :rtype: SystemPurposeData instance
        """
        system_purpose_data = SystemPurposeData()

        try:
            syspurpose_json = json.loads(final_syspurpose_json)
        except json.decoder.JSONDecodeError:
            log.warning("subscription: failed to parse GetSyspurpose() JSON output")
            # empty system purpose data is better than an installation ending crash
            return system_purpose_data

        system_purpose_data.role = syspurpose_json.get(
            "role",
            ""
        )
        system_purpose_data.sla = syspurpose_json.get(
            "service_level_agreement",
            ""
        )
        system_purpose_data.usage = syspurpose_json.get(
            "usage",
            ""
        )
        system_purpose_data.addons = syspurpose_json.get(
            "addons",
            []
        )
        return system_purpose_data

    def run(self):
        """Get data from RHSM describing what subscriptions have been attached to the system.

        Calling the AutoAttach() over RHSM DBus API also generally returns such data,
        but due to bug 1790924,  we can't depend on it always being the case.

        Therefore, we query subscription state separately using the GetPools() method.

        We also retrieve system purpose data from the system, as registration that
        uses an activation key with custom system purpose value attached, can result
        in system purpose data being different after registration.
        """
        locale = os.environ.get("LANG", "")
        # fetch final system purpose data
        log.debug("subscription: fetching final syspurpose data")
        final_syspurpose_json = self._rhsm_syspurpose_proxy.GetSyspurpose(locale)
        log.debug("subscription: final syspurpose data: %s", final_syspurpose_json)

        # parse the JSON strings
        system_purpose_data = self._parse_system_purpose_json(final_syspurpose_json)

        # return the DBus structures as a named tuple
        return SystemSubscriptionData(system_purpose_data=system_purpose_data)


class DownloadSatelliteProvisioningScriptTask(Task):
    """Download the provisioning script from a Satellite instance."""

    def __init__(self, satellite_url, proxy_url):
        """Create a new Satellite related task.

        :param str satellite_url: URL to Satellite instace to download from
        :param str proxy_url: proxy URL for the download attempt
        """
        super().__init__()
        self._satellite_url = satellite_url
        self._proxy_url = proxy_url

    @property
    def name(self):
        return "Download Satellite provisioning script"

    def run(self):
        log.debug("subscription: downloading Satellite provisioning script")
        return satellite.download_satellite_provisioning_script(
            satellite_url=self._satellite_url,
            proxy_url=self._proxy_url
        )


class RunSatelliteProvisioningScriptTask(Task):
    """Run the provisioning script we downloaded from a Satellite instance."""

    def __init__(self, provisioning_script):
        """Create a new Satellite related task.

        :param str provisioning_script: Satellite provisioning script in string form
        """
        super().__init__()
        self._provisioning_script = provisioning_script

    @property
    def name(self):
        return "Run Satellite provisioning script"

    def run(self):
        log.debug("subscription: running Satellite provisioning script"
                  " in installation environment")

        provisioning_success = satellite.run_satellite_provisioning_script(
            provisioning_script=self._provisioning_script,
            run_on_target_system=False
        )

        if provisioning_success:
            log.debug("subscription: Satellite provisioning script executed successfully")
        else:
            message = "Failed to run Satellite provisioning script."
            raise SatelliteProvisioningError(message)


class BackupRHSMConfBeforeSatelliteProvisioningTask(Task):
    """Backup the RHSM configuration state before the Satellite provisioning script is run.

    The Satellite provisioning script sets arbitrary RHSM configuration options, which
    we might need to roll back in case the user decides to unregister and then register
    to a different Satellite instance or back to Hosted Candlepin.

    So backup the RHSM configuration state just before we run the Satellite provisioning
    script that changes the config file. This gives us a config snapshot we can then use
    to restore the RHSM configuration to a "clean" state as needed.
    """

    def __init__(self, rhsm_config_proxy):
        """Create a new Satellite related task.

        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy

    @property
    def name(self):
        return "Save RHSM configuration before Satellite provisioning"

    def run(self):
        # retrieve a snapshot of "clean" RHSM configuration and return it
        return get_native(self._rhsm_config_proxy.GetAll(""))


class RollBackSatelliteProvisioningTask(Task):
    """Roll back relevant parts of Satellite provisioning.

    The current Anaconda GUI makes it possible to unregister and
    change the Satellite URL as well as switch back from Satellite
    to registration on Hosted Candlepin.

    Due to this we need to be able to roll back changes to the RHSM
    configuration done by the Satellite provisioning script.

    To make this possible we first save a "clean" snapshot of the RHSM
    config state so that this task can then restore the snapshot as
    needed.

    We don't actually uninstall the certs added by the provisioning
    script, but they should not interfere with another run of a different
    script & will be gone after the installation environment restarts.
    """

    def __init__(self, rhsm_config_proxy, rhsm_configuration):
        """Create a new Satellite related task.

        :param rhsm_config_proxy: DBus proxy for the RHSM Config object
        :param dict rhsm_configuration: flat "clean" RHSM configuration dict to restore
        """
        super().__init__()
        self._rhsm_config_proxy = rhsm_config_proxy
        self._rhsm_configuration = rhsm_configuration

    @property
    def name(self):
        return "Restore RHSM configuration after Satellite provisioning"

    def run(self):
        """Restore the full RHSM configuration back to clean values."""
        # the SetAll() RHSM DBus API requires a dict of variants
        config_dict = {}
        for key, value in self._rhsm_configuration.items():
            # if value is present in request, use it
            config_dict[key] = get_variant(Str, value)
        self._rhsm_config_proxy.SetAll(config_dict, "")


class RegisterAndSubscribeTask(Task):
    """Register and subscribe the installation environment.

    NOTE: A separate installation task make sure all the subscription related tokens
          and configuration files are transferred to the target system, to keep
          the machine subscribed also after installation.

          In case of registration to a Satellite instance another installation task
          makes sure the system stays registered to Satellite after installation.
    """

    def __init__(self, rhsm_observer, subscription_request, system_purpose_data,
                 registered_callback, registered_to_satellite_callback,
                 simple_content_access_callback, subscription_attached_callback,
                 subscription_data_callback, satellite_script_callback,
                 config_backup_callback):
        """Create a register-and-subscribe task.

        :param rhsm_observer: DBus service observer for talking to RHSM
        :param subscription_request: subscription request DBus struct
        :param system_purpose_data: system purpose DBus struct

        :param registered_callback: called when registration tasks finishes successfully
        :param registered_to_satellite_callback: called after successful Satellite provisioning
        :param simple_content_access_callback: called when registration tasks finishes successfully
        :param subscription_attached_callback: called after subscription is attached
        :param subscription_data_callback: called after subscription data is parsed
        :param satellite_script_callback: called after Satellite provisioning script
                                          has been downloaded
        :param config_backup_callback: called when RHSM config data is ready to be backed up

        :raises: SatelliteProvisioningError if Satellite provisioning fails
        :raises: RegistrationError if registration fails
        :raises: MultipleOrganizationsError if account is multiorg but no org id specified
        """
        super().__init__()
        self._rhsm_observer = rhsm_observer
        self._subscription_request = subscription_request
        self._system_purpose_data = system_purpose_data
        self._rhsm_configuration = {}
        # callback for nested tasks
        self._registered_callback = registered_callback
        self._registered_to_satellite_callback = registered_to_satellite_callback
        self._simple_content_access_callback = simple_content_access_callback
        self._subscription_attached_callback = subscription_attached_callback
        self._subscription_data_callback = subscription_data_callback
        self._satellite_script_downloaded_callback = satellite_script_callback
        self._config_backup_callback = config_backup_callback

    @property
    def name(self):
        return "Register and subscribe"

    @staticmethod
    def _get_proxy_url(subscription_request):
        """Construct proxy URL from proxy data (if any) in subscription request.

        :param subscription_request: subscription request DBus struct
        :return: proxy URL string or None if subscription request contains no usable proxy data
        :rtype: Str or None
        """
        proxy_url = None
        # construct proxy URL needed by the task from the
        # proxy data in subscription request (if any)
        # (it is logical to use the same proxy for provisioning
        #  script download as for RHSM access)
        if subscription_request.server_proxy_hostname:
            proxy = ProxyString(host=subscription_request.server_proxy_hostname,
                                username=subscription_request.server_proxy_user,
                                password=subscription_request.server_proxy_password.value)
            # only set port if valid in the struct (not -1):
            if subscription_request.server_proxy_port != -1:
                # ProxyString expects the port to be a string
                proxy.port = str(subscription_request.server_proxy_port)
                # refresh the ProxyString internal URL cache after setting the port number
                proxy.parse_components()
            proxy_url = str(proxy)
        return proxy_url

    @staticmethod
    def _detect_sca_from_registration_data(registration_data_json):
        """Detect SCA/entitlement mode from registration data.

        This function checks JSON data describing registration state as returned
        by the the Register() or RegisterWithActivationKeys() RHSM DBus methods.
        Based on the value of the "contentAccessMode" key present in a dictionary available
        under the "owner" top level key.

        :param str registration_data_json: registration data in JSON format
        :return: True if data inicates SCA enabled, False otherwise
        """
        # we can't try to detect SCA mode if we don't have any registration data
        if not registration_data_json:
            log.warning("no registraton data provided, skipping SCA mode detection attempt")
            return False
        registration_data = json.loads(registration_data_json)
        owner_data = registration_data.get("owner")

        if owner_data:
            content_access_mode = owner_data.get("contentAccessMode")
            if content_access_mode == "org_environment":
                # SCA explicitely noted as enabled
                return True
            elif content_access_mode == "entitlement":
                # SCA explicitely not enabled
                return False
            else:
                log.warning("contentAccessMode mode not set to known value:")
                log.warning(content_access_mode)
                # unknown mode or missing data -> not SCA
                return False
        else:
            # we have no data indicating SCA is enabled
            return False

    def _provision_system_for_satellite(self):
        """Provision the installation environment for a Satellite instance.

        This method is speculatively run if custom server hostname has been
        set by the user. Only if the URL specified by the server hostname
        contains Satellite provisioning artifacts then actually provisioning
        of installation environment will take place.

        """
        # First check if the server_hostname has the not-satellite prefix.
        # If it does have the prefix, log the fact and skip Satellite provisioning.
        if self._subscription_request.server_hostname.startswith(
            SERVER_HOSTNAME_NOT_SATELLITE_PREFIX
        ):
            log.debug("registration attempt: server hostname marked as not Satellite URL")
            log.debug("registration attempt: skipping Satellite provisioning")
            return

        # create the download task
        provisioning_script = None
        download_task = DownloadSatelliteProvisioningScriptTask(
            satellite_url=self._subscription_request.server_hostname,
            proxy_url=self._get_proxy_url(self._subscription_request)
        )

        # run the download task
        try:
            log.debug("registration attempt: downloading Satellite provisioning script")
            provisioning_script = download_task.run()
            log.debug("registration attempt: downloaded Satellite provisioning script")
            self._satellite_script_downloaded_callback(provisioning_script)
        except SatelliteProvisioningError as e:
            log.debug("registration attempt: failed to download Satellite provisioning script")
            # Failing to download the Satellite provisioning script for a user provided
            # server hostname is an unrecoverable error (wrong URL or incorrectly configured
            # Satellite instance), so we end there.
            raise e

        # before running the Satellite provisioning script we back up the current RHSM config
        # file state, so that we can restore it if Satellite provisioning rollback become necessary
        rhsm_config_proxy = self._rhsm_observer.get_proxy(RHSM_CONFIG)
        backup_task = BackupRHSMConfBeforeSatelliteProvisioningTask(
            rhsm_config_proxy=rhsm_config_proxy
        )
        # Run the task and flatten the returned configuration
        # (so that it can be fed to SetAll()) now, so we don't have to do that later.
        flat_rhsm_configuration = {}
        nested_rhsm_configuration = backup_task.run()
        if nested_rhsm_configuration:
            flat_rhsm_configuration = flatten_rhsm_nested_dict(nested_rhsm_configuration)
        self._config_backup_callback(flat_rhsm_configuration)
        # also store a copy in this task, in case we encounter an error and need to roll-back
        # when this task is still running
        self._rhsm_configuration = flat_rhsm_configuration

        # now run the Satellite provisioning script we just downloaded, so that the installation
        # environment can talk to the Satellite instance the user has specified via custom
        # server hostname
        run_script_task = RunSatelliteProvisioningScriptTask(
            provisioning_script=provisioning_script
        )
        run_script_task.succeeded_signal.connect(
            lambda: self._registered_to_satellite_callback(True)
        )
        try:
            log.debug("registration attempt: running Satellite provisioning script")
            run_script_task.run_with_signals()
            log.debug("registration attempt: Satellite provisioning script has been run")
            # unfortunately the RHSM service apparently does not pick up the changes done
            # by the provisioning script to rhsm.conf, so we need to restart the RHSM systemd
            # service, which will make it re-read the config file
            service.restart_service(RHSM_SERVICE_NAME)

        except SatelliteProvisioningError as e:
            log.debug("registration attempt: Satellite provisioning script run failed")
            # Failing to run the Satellite provisioning script successfully,
            # which is an unrecoverable error, so we end there.
            raise e

    def _roll_back_satellite_provisioning(self):
        """Something failed after we did Satellite provisioning - roll it back."""
        log.debug("registration attempt: rolling back Satellite provisioning")
        rollback_task = RollBackSatelliteProvisioningTask(
            rhsm_config_proxy=self._rhsm_observer.get_proxy(RHSM_CONFIG),
            rhsm_configuration=self._rhsm_configuration
        )
        rollback_task.run()
        log.debug("registration attempt: Satellite provisioning rolled back")

    def run(self):
        """Try to register and subscribe the installation environment."""
        provisioned_for_satellite = False
        # check authentication method has been set and credentials seem to be
        # sufficient (though not necessarily valid)
        register_task = None
        if self._subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD:
            if username_password_sufficient(self._subscription_request):
                username = self._subscription_request.account_username
                password = self._subscription_request.account_password.value
                organization = self._subscription_request.account_organization
                register_server_proxy = self._rhsm_observer.get_proxy(RHSM_REGISTER_SERVER)
                register_task = RegisterWithUsernamePasswordTask(
                        rhsm_register_server_proxy=register_server_proxy,
                        username=username,
                        password=password,
                        organization=organization
                )
        elif self._subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_ORG_KEY:
            if org_keys_sufficient(self._subscription_request):
                organization = self._subscription_request.organization
                activation_keys = self._subscription_request.activation_keys.value
                register_server_proxy = self._rhsm_observer.get_proxy(RHSM_REGISTER_SERVER)
                register_task = RegisterWithOrganizationKeyTask(
                    rhsm_register_server_proxy=register_server_proxy,
                    organization=organization,
                    activation_keys=activation_keys
                )
        if register_task:
            # Now that we know we can do a registration attempt:
            # 1) Connect task success callbacks.
            register_task.succeeded_signal.connect(lambda: self._registered_callback(True))
            # set SCA state based on data returned by the registration task
            register_task.succeeded_signal.connect(
                lambda: self._simple_content_access_callback(
                    self._detect_sca_from_registration_data(register_task.get_result())
                )
            )

            # 2) Check if custom server hostname is set, which would indicate we are most
            #    likely talking to a Satellite instance. If so, provision the installation
            #    environment for that Satellite instance.
            if self._subscription_request.server_hostname:
                # if custom server hostname is set, attempt to provision the installation
                # environment for Satellite
                log.debug("registration attempt: provisioning system for Satellite")
                self._provision_system_for_satellite()
                provisioned_for_satellite = True
                # if we got there without an exception being raised, it was a success!
                log.debug("registration attempt: system provisioned for Satellite")

            # run the registration task
            try:
                register_task.run_with_signals()
            except (RegistrationError, MultipleOrganizationsError) as e:
                log.debug("registration attempt: registration attempt failed: %s", e)
                if provisioned_for_satellite:
                    self._roll_back_satellite_provisioning()
                raise e
            log.debug("registration attempt: registration succeeded")
        else:
            log.debug(
                "registration attempt: credentials insufficient, skipping registration attempt"
            )
            if provisioned_for_satellite:
                self._roll_back_satellite_provisioning()
            raise RegistrationError(_("Registration failed due to insufficient credentials."))

        # if we got this far without an exception then subscriptions have been attached
        self._subscription_attached_callback(True)

        # parse attached subscription data
        log.debug("registration attempt: parsing attached subscription data")
        rhsm_syspurpose_proxy = self._rhsm_observer.get_proxy(RHSM_SYSPURPOSE)
        parse_task = ParseSubscriptionDataTask(rhsm_syspurpose_proxy=rhsm_syspurpose_proxy)
        parse_task.succeeded_signal.connect(
            lambda: self._subscription_data_callback(parse_task.get_result())
        )
        parse_task.run_with_signals()


class RetrieveOrganizationsTask(Task):
    """Obtain data about the organizations the given Red Hat account is a member of.

    While it is apparently not possible for a Red Hat account account to be a member
    of multiple organizations on the Red Hat run subscription infrastructure
    (hosted candlepin), its is a regular occurrence for accounts used for customer
    Satellite instances.
    """

    # the cache is used to serve last-known-good data if calling the GetOrgs()
    # DBus method can't be called successfully in some scenarios
    _org_data_list_cache = []

    def __init__(self, rhsm_register_server_proxy, username, password, reset_cache=False):
        """Create a new organization data parsing task.

        :param rhsm_register_server_proxy: DBus proxy for the RHSM RegisterServer object
        :param str username: Red Hat account username
        :param str password: Red Hat account password
        :param bool reset_cache: clear the cache before calling GetOrgs()
        """
        super().__init__()
        self._rhsm_register_server_proxy = rhsm_register_server_proxy
        self._username = username
        self._password = password
        self._reset_cache = reset_cache

    @property
    def name(self):
        return "Retrieve organizations"

    @staticmethod
    def _parse_org_data_json(org_data_json):
        """Parse JSON data about organizations this Red Hat account belongs to.

        As an account might be a member of multiple organizations,
        the JSON data is an array of dictionaries, with one dictionary per organization.

        :param str org_data_json: JSON describing organizations the given account belongs to
        :return: data about the organizations the account belongs to
        :rtype: list of OrganizationData instances
        """
        try:
            org_json = json.loads(org_data_json)
        except json.decoder.JSONDecodeError:
            log.warning("subscription: failed to parse GetOrgs() JSON output")
            # empty system purpose data is better than an installation ending crash
            return []

        org_data_list = []
        for single_org in org_json:
            org_data = OrganizationData()
            # machine readable organization id
            org_data.id = single_org.get("key", "")
            # human readable organization name
            org_data.name = single_org.get("displayName", "")
            # finally, append to the list
            org_data_list.append(org_data)

        return org_data_list

    def run(self):
        """Parse organization data for a Red Hat account username and password.

        :raises: RegistrationError if calling the RHSM DBus API returns an error
        """
        # reset the data cache if requested
        if self._reset_cache:
            RetrieveOrganizationsTask._org_data_list_cache = []
        log.debug("subscription: getting data about organizations")
        with RHSMPrivateBus(self._rhsm_register_server_proxy) as private_bus:
            try:
                locale = os.environ.get("LANG", "")
                private_register_proxy = private_bus.get_proxy(
                    RHSM.service_name,
                    RHSM_REGISTER.object_path
                )

                org_data_json = private_register_proxy.GetOrgs(
                    self._username,
                    self._password,
                    {},
                    locale
                )

                log.debug("subscription: got organization data (%d characters)",
                          len(org_data_json))

                # parse the JSON strings into list of DBus data objects
                org_data = self._parse_org_data_json(org_data_json)

                log.debug("subscription: updating org data cache")
                RetrieveOrganizationsTask._org_data_list_cache = org_data
                # return the DBus structure list
                return org_data
            except DBusError as e:
                # Errors returned by the RHSM DBus API for this call are unfortunately
                # quite ambiguous (especially if Hosted Candlepin is used) and we can't
                # really decide which are fatal and which are not.
                # So just log the full error JSON from the message field of the returned
                # DBus exception and return empty organization list.
                # If there really is something wrong with the credentials or RHSM
                # configuration it will prevent the next stage - registration - from
                # working anyway.
                log.debug("subscription: failed to get organization data")
                # log the raw exception JSON payload for debugging purposes
                log.debug(str(e))
                # if we have something in cache, log the cache is being used,
                # if there is nothing don't log anything as the cache is empty
                if RetrieveOrganizationsTask._org_data_list_cache:
                    log.debug("subscription: using cached organization data after failure")
                return RetrieveOrganizationsTask._org_data_list_cache

    def for_publication(self):
        """Return a DBus representation."""
        return RetrieveOrganizationsTaskInterface(self)
