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
import json

from dasbus.typing import get_variant, Str
from dasbus.connection import MessageBus
from dasbus.error import DBusError

from pyanaconda.core.i18n import _

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.constants.objects import RHSM_REGISTER
from pyanaconda.modules.common.errors.subscription import RegistrationError, \
    UnregistrationError, SubscriptionError

from pyanaconda.anaconda_loggers import get_module_logger
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

    def __exit__(self, exc_type, exc_value, exc_traceback):
        log.debug("subscription: shutting down the RHSM private DBus session")
        self.connection.disconnect()
        locale = os.environ.get("LANG", "")
        self._rhsm_register_server_proxy.Stop(locale)
        log.debug("subscription: RHSM private DBus session has been shutdown")

    def _get_connection(self):
        """Get a connection to RHSM private DBus session."""
        # the RHSM private bus address is potentially sensitive
        # so we will not log it
        log.info("Connecting to the RHSM private DBus session.")
        return self._provider.get_addressed_bus_connection(self._private_bus_address)


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
        property_key_map = {
            self.CONFIG_KEY_SERVER_HOSTNAME: self._request.server_hostname,
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

    def __init__(self, rhsm_register_server_proxy, username, password):
        """Create a new registration task.

        It is assumed the username and password have been
        validated before this task has been started.

        :param rhsm_register_server_proxy: DBus proxy for the RHSM RegisterServer object
        :param str username: Red Hat account username
        :param str password: Red Hat account password
        """
        super().__init__()
        self._rhsm_register_server_proxy = rhsm_register_server_proxy
        self._username = username
        self._password = password

    @property
    def name(self):
        return "Register with Red Hat account username and password"

    def run(self):
        """Register the system with Red Hat account username and password.

        :raises: RegistrationError if calling the RHSM DBus API returns an error
        """
        log.debug("subscription: registering with username and password")
        with RHSMPrivateBus(self._rhsm_register_server_proxy) as private_bus:
            try:
                locale = os.environ.get("LANG", "")
                private_register_proxy = private_bus.get_proxy(RHSM.service_name,
                                                               RHSM_REGISTER.object_path)
                # We do not yet support setting organization for username & password
                # registration, so organization is blank for now.
                organization = ""
                private_register_proxy.Register(organization,
                                                self._username,
                                                self._password,
                                                {},
                                                {},
                                                locale)
                log.debug("subscription: registered with username and password")
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
        """
        log.debug("subscription: registering with organization and activation key")
        with RHSMPrivateBus(self._rhsm_register_server_proxy) as private_bus:
            try:
                locale = os.environ.get("LANG", "")
                private_register_proxy = private_bus.get_proxy(RHSM.service_name,
                                                               RHSM_REGISTER.object_path)
                private_register_proxy.RegisterWithActivationKeys(self._organization,
                                                                  self._activation_keys,
                                                                  {},
                                                                  {},
                                                                  locale)
                log.debug("subscription: registered with organization and activation key")
            except DBusError as e:
                log.debug("subscription: failed to register with organization & key: %s", str(e))
                # RHSM exception contain details as JSON due to DBus exception handling limitations
                exception_dict = json.loads(str(e))
                # return a generic error message in case the RHSM provided error message is missing
                message = exception_dict.get("message", _("Registration failed."))
                raise RegistrationError(message) from None


class UnregisterTask(Task):
    """Unregister the system."""

    def __init__(self, rhsm_unregister_proxy):
        """Create a new unregistration task.

        :param rhsm_unregister_proxy: DBus proxy for the RHSM Unregister object
        """
        super().__init__()
        self._rhsm_unregister_proxy = rhsm_unregister_proxy

    @property
    def name(self):
        return "Unregister the system"

    def run(self):
        """Unregister the system."""
        log.debug("subscription: unregistering the system")
        try:
            locale = os.environ.get("LANG", "")
            self._rhsm_unregister_proxy.Unregister({}, locale)
            log.debug("subscription: the system has been unregistered")
        except DBusError as e:
            log.exception("subscription: failed to unregister: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Unregistration failed."))
            raise UnregistrationError(message) from None


class AttachSubscriptionTask(Task):
    """Attach a subscription."""

    def __init__(self, rhsm_attach_proxy, sla):
        """Create a new subscription task.

        :param rhsm_attach_proxy: DBus proxy for the RHSM Attach object
        :param str sla: organization name for subscription purposes
        """
        super().__init__()
        self._rhsm_attach_proxy = rhsm_attach_proxy
        self._sla = sla

    @property
    def name(self):
        return "Attach a subscription"

    def run(self):
        """Attach a subscription to the installation environment.

        This subscription will be used for CDN access during the
        installation and then transferred to the target system
        via separate DBus task.

        :raises: SubscriptionError if RHSM API DBus call fails
        """
        log.debug("subscription: auto-attaching a subscription")
        try:
            locale = os.environ.get("LANG", "")
            result = self._rhsm_attach_proxy.AutoAttach(self._sla, {}, locale)
            log.debug("subscription: auto-attached a subscription")
        except DBusError as e:
            log.debug("subscription: auto-attach failed: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Failed to attach subscription."))
            raise SubscriptionError(message) from None
