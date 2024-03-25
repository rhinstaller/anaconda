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
import datetime
from collections import namedtuple

from dasbus.typing import get_variant, Str
from dasbus.connection import MessageBus
from dasbus.error import DBusError

from pyanaconda.core.i18n import _
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.constants.objects import RHSM_REGISTER
from pyanaconda.modules.common.errors.subscription import RegistrationError, \
    UnregistrationError, SubscriptionError
from pyanaconda.modules.common.structures.subscription import AttachedSubscription, \
    SystemPurposeData
from pyanaconda.modules.subscription import system_purpose
from pyanaconda.anaconda_loggers import get_module_logger

import gi
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
                                    ["attached_subscriptions", "system_purpose_data"])


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
            self._rhsm_attach_proxy.AutoAttach(self._sla, {}, locale)
            log.debug("subscription: auto-attached a subscription")
        except DBusError as e:
            log.debug("subscription: auto-attach failed: %s", str(e))
            exception_dict = json.loads(str(e))
            # return a generic error message in case the RHSM provided error message
            # is missing
            message = exception_dict.get("message", _("Failed to attach subscription."))
            raise SubscriptionError(message) from None


class ParseAttachedSubscriptionsTask(Task):
    """Parse data about subscriptions attached to the installation environment."""

    def __init__(self, rhsm_entitlement_proxy, rhsm_syspurpose_proxy):
        """Create a new attached subscriptions parsing task.

        :param rhsm_entitlement_proxy: DBus proxy for the RHSM Entitlement object
        :param rhsm_syspurpose_proxy: DBus proxy for the RHSM Syspurpose object
        """
        super().__init__()
        self._rhsm_entitlement_proxy = rhsm_entitlement_proxy
        self._rhsm_syspurpose_proxy = rhsm_syspurpose_proxy

    @property
    def name(self):
        return "Parse attached subscription data"

    @staticmethod
    def _pretty_date(date_from_json):
        """Return pretty human readable date based on date from the input JSON."""
        # fallback in case of the parsing fails
        date_string = date_from_json
        # try to parse the date as ISO 8601 first
        try:
            date = datetime.datetime.strptime(date_from_json, "%Y-%m-%d")
            # get a nice human readable date
            return date.strftime("%b %d, %Y")
        except ValueError:
            pass
        try:
            # The start/end date in GetPools() output seems to be formatted as
            # "Locale's appropriate date representation.".
            # See bug 1793501 for possible issues with RHSM provided date parsing.
            date = datetime.datetime.strptime(date_from_json, "%m/%d/%y")
            # get a nice human readable date
            date_string = date.strftime("%b %d, %Y")
        except ValueError:
            log.warning("subscription: date parsing failed: %s", date_from_json)
        return date_string

    @classmethod
    def _parse_subscription_json(cls, subscription_json):
        """Parse the JSON into list of AttachedSubscription instances.

        The expected JSON is at top level a list of rather complex dictionaries,
        with each dictionary describing a single subscription that has been attached
        to the system.

        :param str subscription_json: JSON describing what subscriptions have been attached
        :return: list of attached subscriptions
        :rtype: list of AttachedSubscription instances
        """
        attached_subscriptions = []
        try:
            subscriptions = json.loads(subscription_json)
        except json.decoder.JSONDecodeError:
            log.warning("subscription: failed to parse GetPools() JSON output")
            # empty attached subscription list is better than an installation
            # ending crash
            return []
        # find the list of subscriptions
        consumed_subscriptions = subscriptions.get("consumed", [])
        log.debug("subscription: parsing %d attached subscriptions",
                  len(consumed_subscriptions))
        # split the list of subscriptions into separate subscription dictionaries
        for subscription_info in consumed_subscriptions:
            attached_subscription = AttachedSubscription()
            # user visible product name
            attached_subscription.name = subscription_info.get(
                "subscription_name",
                _("product name unknown")
            )

            # subscription support level
            # - this does *not* seem to directly correlate to system purpose SLA attribute
            attached_subscription.service_level = subscription_info.get(
                "service_level",
                _("unknown")
            )

            # SKU
            # - looks like productId == SKU in this JSON output
            attached_subscription.sku = subscription_info.get(
                "sku",
                _("unknown")
            )

            # contract number
            attached_subscription.contract = subscription_info.get(
                "contract",
                _("not available")
            )

            # subscription start date
            # - convert the raw date data from JSON to something more readable
            start_date = subscription_info.get(
                "starts",
                _("unknown")
            )
            attached_subscription.start_date = cls._pretty_date(start_date)

            # subscription end date
            # - convert the raw date data from JSON to something more readable
            end_date = subscription_info.get(
                "ends",
                _("unknown")
            )
            attached_subscription.end_date = cls._pretty_date(end_date)

            # consumed entitlements
            # - this seems to correspond to the toplevel "quantity" key,
            #   not to the pool-level "consumed" key for some reason
            #   *or* the pool-level "quantity" key
            quantity_string = int(subscription_info.get("quantity_used", 1))
            attached_subscription.consumed_entitlement_count = quantity_string
            # add attached subscription to the list
            attached_subscriptions.append(attached_subscription)
        # return the list of attached subscriptions
        return attached_subscriptions

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
        # fetch subscription status data
        subscription_json = self._rhsm_entitlement_proxy.GetPools(
            {"pool_subsets": get_variant(Str, "consumed")},
            {},
            locale
        )
        subscription_data_length = 0
        # Log how much subscription data we got for debugging purposes.
        # By only logging length, we should be able to debug cases of no
        # or incomplete data being logged, without logging potentially
        # sensitive subscription status detail into the installation logs
        # stored on the target system.
        if subscription_json:
            subscription_data_length = len(subscription_json)
            log.debug("subscription: fetched subscription status data: %d characters",
                      subscription_data_length)
        else:
            log.warning("subscription: fetched empty subscription status data")

        # fetch final system purpose data
        log.debug("subscription: fetching final syspurpose data")
        final_syspurpose_json = self._rhsm_syspurpose_proxy.GetSyspurpose(locale)
        log.debug("subscription: final syspurpose data: %s", final_syspurpose_json)

        # parse the JSON strings
        attached_subscriptions = self._parse_subscription_json(subscription_json)
        system_purpose_data = self._parse_system_purpose_json(final_syspurpose_json)

        # return the DBus structures as a named tuple
        return SystemSubscriptionData(attached_subscriptions=attached_subscriptions,
                                      system_purpose_data=system_purpose_data)
