#
# Kickstart module for subscription handling.
#
# Copyright (C) 2019 Red Hat, Inc.
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

from pyanaconda.core import util

from pyanaconda.dbus import DBus, SystemBus
from pyanaconda.dbus.typing import get_variant, Str
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.constants.objects import RHSM_CONFIG, RHSM_SYSPURPOSE, \
        RHSM_ENTITLEMENT
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification
from pyanaconda.modules.subscription.constants import AuthenticationMethod
from pyanaconda.modules.subscription.installation import SystemPurposeConfigurationTask
from pyanaconda.modules.subscription.installation import RegisterWithUsernamePasswordTask, \
        RegisterWithOrganizationKeyTask, AttachSubscriptionTask, UnregisterTask
from pyanaconda.modules.subscription.installation import SubscriptionTaskInterface
from pyanaconda.modules.subscription.installation import TransferSubscriptionTokensTask
from pyanaconda.modules.subscription.installation import ConnectToInsightsTask
from pyanaconda.modules.subscription.subscription_data import SubscriptionData
from pyanaconda.modules.subscription import system_purpose

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SubscriptionModule(KickstartModule):
    """The Subscription module."""

    def __init__(self):
        super().__init__()

        # system purpose
        self._valid_roles = {}
        self.role_changed = Signal()
        self._role = ""

        self._valid_slas = {}
        self.sla_changed = Signal()
        self._sla = ""

        self._valid_usage_types = {}
        self.usage_changed = Signal()
        self._usage = ""

        self.addons_changed = Signal()
        self._addons = []

        self._is_system_purpose_applied = False
        self.is_system_purpose_applied_changed = Signal()

        self.is_system_purpose_set_changed = Signal()
        self.role_changed.connect(self.is_system_purpose_set_changed.emit)
        self.sla_changed.connect(self.is_system_purpose_set_changed.emit)
        self.usage_changed.connect(self.is_system_purpose_set_changed.emit)
        self.addons_changed.connect(self.is_system_purpose_set_changed.emit)

        self._load_valid_values()

        # cached rhsm proxies
        self._rhsm_proxy = None
        self._rhsm_config_proxy = None

        # subscription

        # make sure /etc/yum.repos.d exists
        self._assure_yum_repos_folder()

        # set initial RHSM options, but only if system bus is available
        if SystemBus.check_connection():
            # set debug log level, so that
            # subscription related issues
            # can be debugged
            self._set_rhsm_log_level("DEBUG")

        self.registered_changed = Signal()
        self._registered = False
        self.subscription_attached_changed = Signal()
        self._subscription_attached = False

        self.attached_subscriptions_changed = Signal()

        # initialize with an empty instance
        self._subscription_data = SubscriptionData()

        # authentication
        self.organization_changed = Signal()
        self._organization = ""

        self.activation_keys_changed = Signal()
        self._activation_keys = []

        self.red_hat_account_username_changed = Signal()
        self._red_hat_account_username = ""

        self.red_hat_account_password_changed = Signal()
        self._red_hat_account_password = ""

        self._authentication_method = AuthenticationMethod.NOT_SELECTED
        self.authentication_method_changed = Signal()

        # custom Candlepin instance URL
        # (naming follows rhsm.conf section & key name)
        self.server_hostname_changed = Signal()
        self._server_hostname = ""
        # we cache the original server hostname (if any)
        # so we can put it back if custom set baseurl
        # is later reverted
        self._original_server_hostname = ""
        self._original_server_hostname_set = False

        # custom CDN baseurl
        # (naming follows rhsm.conf section & key name)
        self.rhsm_baseurl_changed = Signal()
        self._rhsm_baseurl = ""
        # we cache the original rhsm baseurl (if any)
        # so we can put it back if custom set baseurl
        # is later reverted
        self._original_rhsm_baseurl = ""
        self._original_rhsm_baseurl_set = False

        # HTTP proxy for RHSM usage
        # (naming follows rhsm.conf section & key name)
        self._server_proxy_hostname = ""
        self._server_proxy_port = -1
        self._server_proxy_user = ""
        self._server_proxy_password = ""
        self.server_proxy_configuration_changed = Signal()

        # Insights
        #
        # What are the default for Red Hat Insights ?
        # - during a kickstart installation, the user
        #   needs to opt-in by using the rhsm command
        #   with the --connect-to-insights option
        # - during a GUI interactive installation the
        #  "connect to Insights" checkbox is checked by default,
        #  making Insights opt-out
        # - in both cases the system also needs to be subscribed,
        #   or else the system can't be connected to Insights
        self._connect_to_insights = False
        self.connect_to_insights_changed = Signal()

    def _load_valid_values(self):
        """Load lists of valid roles, SLAs and usage types.

        About role/sla/validity:
        - an older installation image might have older list of valid fields,
          missing fields that have become valid after the image has been released
        - fields that have been valid in the past might be dropped in the future
        - there is no list of valid addons

        Due to this we need to take into account that the listing might not always be
        comprehensive and that we need to allow what might on a first glance look like
        invalid values to be written to the target system.
        """
        roles, slas, usage_types = system_purpose.get_valid_fields()
        self._valid_roles = roles
        self._valid_slas = slas
        self._valid_usage_types = usage_types

    def publish(self):
        """Publish the module."""
        interface_instance = SubscriptionInterface(self)
        DBus.publish_object(SUBSCRIPTION.object_path, interface_instance)
        DBus.register_service(SUBSCRIPTION.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return SubscriptionKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        # system purpose
        #
        # Try if any of the values in kickstart match a valid field.
        # If it does, write the valid field value instead of the value from kickstart.
        #
        # This way a value in kickstart that has a different case and/or trailing white space
        # can still be used to preselect a value in a UI instead of being marked as a custom
        # user specified value.
        self._process_role(data)
        self._process_sla(data)
        self._process_usage(data)

        # we don't have any list of valid addons and addons are not shown in the UI,
        # so we just forward the values from kickstart
        if data.syspurpose.addons:
            self.set_addons(data.syspurpose.addons)

        # credentials
        if data.rhsm.organization:
            self.set_organization(data.rhsm.organization)
        if data.rhsm.activation_keys:
            self.set_activation_keys(data.rhsm.activation_keys)

        # custom URLs
        if data.rhsm.server_hostname:
            self.set_server_hostname(data.rhsm.server_hostname)
        if data.rhsm.rhsm_baseurl:
            self.set_rhsm_baseurl(data.rhsm.rhsm_baseurl)

        # HTTP proxy
        if data.rhsm.proxy:
            # first try to parse the proxy string from kickstart
            try:
                proxy = util.ProxyString(data.rhsm.proxy)
                if proxy.host:
                    # ensure port is an integer and set to -1 if unknown
                    port = int(proxy.port) if proxy.port else -1

                    self.set_server_proxy(hostname=proxy.host,
                                          port=port,
                                          username=proxy.username,
                                          password=proxy.password)
            except util.ProxyStringError as e:
                log.error("Failed to parse proxy for the rhsm command: %s", str(e))

        # apply system purpose data, if any, before starting the RHSM service, so that
        # it picks the values up once started
        if self.is_system_purpose_set:
            self._apply_syspurpose()

        # if org and activation key are set, set authentication method
        # to organization and activation key
        if self.organization and self.activation_keys:
            self.set_authentication_method(AuthenticationMethod.ORG_KEY)

        # insights
        self.set_connect_to_insights(bool(data.rhsm.connect_to_insights))

    def _process_role(self, data):
        if data.syspurpose.role:
            role_match = system_purpose.match_field(data.syspurpose.role, self.valid_roles)
        else:
            role_match = None

        if role_match:
            log.info("role value %s from kickstart matched to know valid field %s", data.syspurpose.role, role_match)
            self.set_role(role_match)
        elif data.syspurpose.role:
            log.info("using custom role value from kickstart: %s", data.syspurpose.role)
            self.set_role(data.syspurpose.role)

    def _process_sla(self, data):
        if data.syspurpose.sla:
            sla_match = system_purpose.match_field(data.syspurpose.sla, self.valid_slas)
        else:
            sla_match = None

        if sla_match:
            log.info("SLA value %s from kickstart matched to know valid field %s", data.syspurpose.sla, sla_match)
            self.set_sla(sla_match)
        elif data.syspurpose.sla:
            log.info("using custom SLA value from kickstart: %s", data.syspurpose.sla)
            self.set_sla(data.syspurpose.sla)

    def _process_usage(self, data):
        if data.syspurpose.usage:
            usage_match = system_purpose.match_field(data.syspurpose.usage, self._valid_usage_types)
        else:
            usage_match = None

        if usage_match:
            log.info("usage value %s from kickstart matched to know valid field %s", data.syspurpose.usage, usage_match)
            self.set_usage(usage_match)
        elif data.syspurpose.usage:
            log.info("using custom usage value from kickstart: %s", data.syspurpose.usage)
            self.set_usage(data.syspurpose.usage)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")

        # system purpose
        data = self.get_kickstart_handler()
        data.syspurpose.role = self.role
        data.syspurpose.sla = self.sla
        data.syspurpose.usage = self.usage
        data.syspurpose.addons = self.addons

        return str(data)

    # utility
    @property
    def rhsm_proxy(self):
        """Return a cached RHSM DBus proxy."""
        if not self._rhsm_proxy:
            self._rhsm_proxy = RHSM.get_proxy()
        return self._rhsm_proxy

    @property
    def rhsm_config_proxy(self):
        """Return a cached RHSM config DBus proxy."""
        if not self._rhsm_config_proxy:
            self._rhsm_config_proxy = RHSM.get_proxy(RHSM_CONFIG)
        return self._rhsm_config_proxy

    # system purpose

    @property
    def valid_roles(self):
        """Return a list of valid roles.

        :return: list of valid roles
        :rtype: list of strings
        """
        return self._valid_roles

    @property
    def role(self):
        """Return the System Purpose role (if any).

        If the system has been subscribed,
        the actual returned is returned, otherwise
        the desired role is returned.
        """
        if self.subscription_attached:
            return self.subscription_data.role
        else:
            return self._role

    def set_role(self, role):
        """Set the role."""
        self._role = role
        self.role_changed.emit()
        log.debug("Role is set to %s.", role)

    @property
    def valid_slas(self):
        """Return a list of valid SLAs.

        :return: list of valid SLAs
        :rtype: list of strings
        """
        return self._valid_slas

    @property
    def sla(self):
        """Return the System Purpose SLA (if any).

        If the system has been subscribed,
        the actual SLA is returned, otherwise
        the desired SLA is returned.
        """
        if self.subscription_attached:
            return self.subscription_data.sla
        else:
            return self._sla

    def set_sla(self, sla):
        """Set the SLA."""
        self._sla = sla
        self.sla_changed.emit()
        log.debug("SLA is set to %s.", sla)

    @property
    def valid_usage_types(self):
        """Return a list of valid usage types.

        :return: list of valid usage types
        :rtype: list of strings
        """
        return self._valid_usage_types

    @property
    def usage(self):
        """Return the System Purpose usage (if any).

        If the system has been subscribed,
        the actual usage is returned, otherwise
        the desired usage is returned.
        """
        if self.subscription_attached:
            return self.subscription_data.usage
        else:
            return self._usage

    def set_usage(self, usage):
        """Set the intended usage."""
        self._usage = usage
        self.usage_changed.emit()
        log.debug("Usage is set to %s.", usage)

    @property
    def addons(self):
        """Return list of additional layered products or features (if any)."""
        return self._addons

    def set_addons(self, addons):
        """Set the intended layered products or features."""
        self._addons = addons
        self.addons_changed.emit()
        log.debug("Addons set to %s.", addons)

    @property
    def is_system_purpose_set(self):
        """Report if system purpose will be set.

        This basically means at least one of role, SLA, usage or addons
        has a user-set non-default value.
        """
        return any((self.role, self.sla, self.usage, self.addons))

    @property
    def is_system_purpose_applied(self):
        """Report if system purpose has been applied to the system.

        Note that we don't differentiate between the installation environment
        and the target system, as the token transfer installation task will
        make sure any system purpose configuration file created in the installation
        environment will be transferred to the target system.
        """
        return self._is_system_purpose_applied

    def _set_is_system_purpose_applied(self, system_purpose_applied):
        """Set if system purpose is applied.

        :param bool system_purpose_applied: True if applied, False otherwise

        NOTE: We keep this as a private method, called by the completed signal of the
              task that applies system purpose information on the system.
        """
        self._is_system_purpose_applied = system_purpose_applied
        self.is_system_purpose_applied_changed.emit()
        log.debug("System purpose is applied set to: %s", system_purpose_applied)

    def set_system_purpose_with_task(self, sysroot):
        """Set system purpose for the installed system with an installation task.

        FIXME: This is just a temporary method.

        :param sysroot: a path to the root of the installed system
        :return: a DBus path of an installation task
        """
        task = SystemPurposeConfigurationTask(sysroot, self.role, self.sla, self.usage, self.addons)
        # set system purpose as applied once the task finishes running
        task.stopped_signal.connect(lambda: self._set_is_system_purpose_applied(True))
        path = self.publish_task(SUBSCRIPTION.namespace, task)
        return path

    # subscription

    @property
    def registered(self):
        """Return True if the system has been registered, False otherwise.

        :return: if the system can be considered as registered
        :rtype: bool
        """
        return self._registered

    def set_registered(self, system_registered):
        """Set that the system has been registered.

        :param bool system_registered: system registered state
        """
        self._registered = system_registered
        self.registered_changed.emit()
        log.debug("System registered set to: %s", system_registered)

    @property
    def subscription_attached(self):
        """Return True if a subscription has been attached to the system.

        :return: if a subscription has been attached to the system
        :rtype: bool
        """
        return self._subscription_attached

    def set_subscription_attached(self, system_subscription_attached):
        """Set a subscription has been attached to the system.

        :param bool system_registered: system attached subscription state
        """
        self._subscription_attached = system_subscription_attached
        self.subscription_attached_changed.emit()
        log.debug("Subscription attached set to: %s", system_subscription_attached)

    @property
    def subscription_data(self):
        """Description of the attached subscription (if any).

        If no subscription is attached, all the properties
        of the Subscription instance return default values.

        :return: description of attached subscription
        :rtype: SubscriptionData instance
        """
        return self._subscription_data

    def clear_subscription_data(self):
        """Clear any previously set subscription data."""
        self._subscription_data = SubscriptionData()
        self.role_changed.emit()
        self.sla_changed.emit()
        self.usage_changed.emit()
        self.attached_subscriptions_changed.emit()

    def set_subscription_data(self, subscription_json, final_syspurpose_json=None):
        """Process the subscription describing JSON data from RHSM.

        Parse the JSON from RHSM into a SubscriptionData class instance
        available via the subscription_data property.

        :param subscription_json: subscription describing JSON data or None if unavailable
        :type subscription_json: str or None
        :param final_syspurpose_json: final syspurpose data in JSON form or None if unavailable
        :type final_syspurpose_json: str or None
        """
        self._subscription_data = SubscriptionData(subscription_json, final_syspurpose_json)

        # Emit signals for properties subscription data being set might influence:
        # - if subscriptions are attached, System Purpose data is served from the
        #   SubscriptionData instance
        # - attached subscription data is always served from the SubscriptionData
        #   instance
        self.role_changed.emit()
        self.sla_changed.emit()
        self.usage_changed.emit()
        self.attached_subscriptions_changed.emit()

    @property
    def attached_subscriptions(self):
        """List attached subscriptions (if any).

        :return: list of attached subscriptions
        :rtype: list of AttachedSubscription instances
        """
        return self.subscription_data.attached_subscriptions

    @property
    def organization(self):
        """Return organization name for subscription purposes.

        Organization name is needed when using an activation key
        and is not needed when registering via Red Hat account
        credentials.

        :return: organization name
        :rtype: str
        """
        return self._organization

    def set_organization(self, organization):
        """Set organization name.

        :param str organization: new organization name
        """
        self._organization = organization
        self.organization_changed.emit()
        log.debug("Organization set to: %s", organization)

    @property
    def activation_keys(self):
        """Return the activation keys used for subscription purposes.

        At least one activation key is needed for successful
        subscription attempt.

        You need to set organization name when using an activation keys.
        :return: activation keys
        :rtype: list of str
        """
        return self._activation_keys

    def set_activation_keys(self, activation_keys):
        """Set the activation key.

        :param activation_key: a list of activation keys
        """
        self._activation_keys = activation_keys
        self.activation_keys_changed.emit()
        if activation_keys:
            key_count = len(activation_keys)
        else:
            key_count = 0
        log.debug("%d activation keys have been set.", key_count)

    @property
    def red_hat_account_username(self):
        """A Red Hat account name for subscription purposes.

        :return: red hat account name
        :rtype: str
        """
        return self._red_hat_account_username

    def set_red_hat_account_username(self, account_username):
        """Set the Red Hat account name.

        :param str account_username: Red Hat account username
        """
        self._red_hat_account_username = account_username
        self.red_hat_account_username_changed.emit()
        log.debug("Red Hat account name set to: %s", account_username)

    @property
    def red_hat_account_password(self):
        """A Red Hat account password for subscription purposes.

        :return: red hat account password
        :rtype: str
        """
        return self._red_hat_account_password

    def set_red_hat_account_password(self, password):
        """Set the Red Hat account name.

        :param str password: Red Hat account password
        """
        self._red_hat_account_password = password
        self.red_hat_account_password_changed.emit()
        log.debug("Red Hat account password has been set.")

    @property
    def authentication_method(self):
        """Return what authentication method has been selected (if any).

        :return: authentication method constant
        :rtype: int
        """
        return self._authentication_method

    def set_authentication_method(self, method):
        """Set authentication method for subscription purposes.

        Based on the selected method, an appropriate DBus task will
        be used at registration time.

        :param int method: authentication method describing constant
        """
        self._authentication_method = method
        self.authentication_method_changed.emit()
        log.debug("RHSM authentication method set to: %s", method)

    @property
    def server_hostname(self):
        """Get the Red Hat subscription service URL.

        Empty string means that the default subscription service
        URL will be used.

        :return: subscription service URL
        :rtype: str
        """
        return self._server_hostname

    def set_server_hostname(self, hostname):
        """Set the Red Hat subscription server hostname.

        This can be used to override the default subscription
        service hostname to a custom one.

        Setting "" as the hostname will revert server hostname
        to the initial value reported by RHSM before we
        have first overridden it.

        :param str hostname: subscription server hostname
        """
        # set the local cached value
        self._server_hostname = hostname

        # if hostname is non-empty, set it to RHSM
        if hostname:
            if self._original_server_hostname_set:
                # save the original server hostname
                self._original_server_hostname = self.rhsm_config_proxy.Get("server.hostname", "")
            # set the custom hostname to RHSM
            self.rhsm_config_proxy.Set("server.hostname", get_variant(Str, hostname), "")
            self._original_server_hostname_set = False
            log.debug("Red Hat subscription server hostname set to: %s", hostname)
        elif self._original_server_hostname:
            # if hostname is empty, restore original value (if available)
            self.rhsm_config_proxy.Set("server.hostname", get_variant(Str, self._original_server_hostname), "")
            self._original_server_hostname_set = True
            log.debug("Red Hat subscription server hostname set back to: %s", self._original_server_hostname)

        self.server_hostname_changed.emit()

    @property
    def rhsm_baseurl(self):
        """Get the Red Hat subscription service URL.

        Empty string means that the default subscription service
        URL will be used.

        :return: subscription service URL
        :rtype: str
        """
        return self._rhsm_baseurl

    def set_rhsm_baseurl(self, baseurl):
        """Set the Red Hat CDN baseurl.

        This can be used to override the default Red Hat CDN
        baseurl to a custom one.

        Setting "" as the baseurl will revert the baseurl
        to the initial value reported by RHSM before we
        have first overridden it.

        :param str baseurl: CDN baseurl
        """
        # set the local cached value
        self._rhsm_baseurl = baseurl

        # if baseurl is non-empty, set it to RHSM
        if baseurl:
            if self._original_rhsm_baseurl_set:
                # save the original CDN baseurl
                self._original_rhsm_baseurl = self.rhsm_config_proxy.Get("rhsm.baseurl", "")
            # set the custom CDN baseurl to RHSM
            self.rhsm_config_proxy.Set("rhsm.baseurl", get_variant(Str, baseurl), "")
            self._original_rhsm_baseurl_set = False
            log.debug("Red Hat CDN baseurl set to: %s", baseurl)
        elif self._original_rhsm_baseurl:
            # if baseurl is empty, restore original value (if available)
            self.rhsm_config_proxy.Set("rhsm.baseurl", get_variant(Str, self._original_rhsm_baseurl), "")
            self._original_rhsm_baseurl_set = True
            log.debug("Red Hat CDN baseurl set back to: %s", self._original_rhsm_baseurl)

        # Due to a bug in RHSM, we need to restart the RHSM DBus service after changing rhsm baseurl
        # or else it might have no effect on subsequent API calls:
        # https://bugzilla.redhat.com/show_bug.cgi?id=1777024
        self._restart_rhsm_service()

        self.rhsm_baseurl_changed.emit()

    @property
    def server_proxy_hostname(self):
        """Get the hostname of the RHSM HTTP proxy.

        Empty string means that no proxy hostname has been set.

        :returns: RHSM HTTP proxy hostname
        :rtype: str
        """
        return self._server_proxy_hostname

    @property
    def server_proxy_port(self):
        """Get the port of the RHSM HTTP proxy.

        -1 means no proxy port has been set.

        :returns: RHSM HTTP proxy port
        :rtype: int
        """
        return self._server_proxy_port

    @property
    def server_proxy_user(self):
        """Get the access username for the RHSM HTTP proxy.

        Empty string means that no username has been set.

        :returns: RHSM HTTP proxy access username
        :rtype: str
        """
        return self._server_proxy_user

    @property
    def server_proxy_password_set(self):
        """Report if the access password for the RHSM HTTP proxy has been set.

        :return: if the access password for RHSM HTTP proxy has been set
        :rtype: bool
        """
        return bool(self._server_proxy_password)

    # pylint: disable=too-many-function-args
    def set_server_proxy(self, hostname, port, username, password):
        """Set configuration of the RHSM HTTP proxy.

        :param str hostname: RHSM HTTP proxy hostname
        :param int port: RHSM HTTP proxy port (set to -1 to clear)
        :param str username: RHSM HTTP proxy access username
        :param str password: RHSM HTTP proxy access password
        """
        # set the local attributes
        self._server_proxy_hostname = hostname
        self._server_proxy_port = port
        # negative port number means no port has been set
        if port < 0:
            port_string = ""
        else:
            port_string = "{}".format(port)
        # use "" when username is not known
        self._server_proxy_user = username or ""

        # use "" when password is not known
        self._server_proxy_password = password or ""

        # set data to RHSM
        log.debug("setting HTTP proxy data to RHSM")
        self.rhsm_config_proxy.Set("server.proxy_hostname",
                                   get_variant(Str, hostname),
                                   "")
        self.rhsm_config_proxy.Set("server.proxy_port",
                                   get_variant(Str, port_string),
                                   "")
        self.rhsm_config_proxy.Set("server.proxy_user",
                                   get_variant(Str, self.server_proxy_user),
                                   "")
        self.rhsm_config_proxy.Set("server.proxy_password",
                                   get_variant(Str, self._server_proxy_password),
                                   "")

        # trigger the changed signal
        self.server_proxy_configuration_changed.emit()
        log.debug("RHSM: HTTP proxy config has been set")

    def _register_task_callback(self, task_instance):
        """Callback triggered after a registration task has been run.

        Check if the task was successful and set module state accordingly.

        :param task_instance: a SubscriptionTask subclass instance
        """
        # if the task failed, nothing should have changed
        if not task_instance.error:
            self.set_registered(True)

    def _unregister_task_callback(self, task_instance):
        """Callback triggered after the unregistration task has been run.

        Check if the task was successful and set module state accordingly.

        :param task_instance: a SubscriptionTask subclass instance
        """

        # if the task failed, nothing should have changed
        if not task_instance.error:
            self.set_registered(False)
            self.set_subscription_attached(False)
            self.clear_subscription_data()

    def _get_subscription_state_data(self):
        """Get data from RHSM describing what subscriptions have been attached to the system.

        Calling AutoAttach() also generally returns such data, but due to bug 1790924,
        we can't depend on it always being the case.

        Therefore, we query subscription state separately using the GetPools() method.
        """

        locale = os.environ.get("LANG", "")
        # fetch subscription status data
        entitlement_proxy = RHSM.get_proxy(RHSM_ENTITLEMENT)
        subscription_json = entitlement_proxy.GetPools(
                {"pool_subsets": get_variant(Str, "consumed")},
                {},
                locale
        )
        subscription_data_length = 0
        # Log how much subscription data we got for debugging purposes.
        # By only logging length, we should be able to debug cases of no
        # or incomplete data being logged, without logging potentially
        # sensitive subscription status detail in the installation logs stored
        # on the target system.
        if subscription_json:
            subscription_data_length = len(subscription_json)
            log.debug("RHSM: fetched subscription status data: %d characters",
                      subscription_data_length)
        else:
            log.warning("RHSM: fetched empty subscription status data")

        # fetch final system purpose data
        log.debug("RHSM: fetching final syspurpose data")
        syspurpose_proxy = RHSM.get_proxy(RHSM_SYSPURPOSE)
        final_syspurpose_json = syspurpose_proxy.GetSyspurpose(locale)
        log.debug("RHSM: final syspurpose data: %s", final_syspurpose_json)

        return subscription_json, final_syspurpose_json

    def _attach_task_callback(self, task_instance):
        """Callback triggered after the auto attach task has been run.

        Check if the task was successful and set module state accordingly.

        :param task_instance: a SubscriptionTask subclass instance
        """
        # if the task failed, nothing should have changed

        if not task_instance.error:
            self.set_subscription_attached(True)

            # retrieve subscription data
            # - for some reason exceptions raised in this method are not logged,
            #   so wrap it in a try-except block for now
            # - as we don't know beforehand what exceptions might be raised by
            #   the method, we also need to disable a pylint warning about
            #   except not specifying a concrete exception to catch
            try:
                subscription_json, syspurpose_json = self._get_subscription_state_data()
            # pylint: disable=broad-except
            except Exception:
                log.exception("RHSM: failed to fetch subscription status data")
            self.set_subscription_data(subscription_json=subscription_json,
                                       final_syspurpose_json=syspurpose_json)

    def attach_subscription_with_task(self):
        """Return path to DBus Task that attaches subscriptions."""
        task = AttachSubscriptionTask(sla=self.sla)
        task.stopped_signal.connect(lambda: self._attach_task_callback(task))
        path = self.publish_task(SUBSCRIPTION.namespace, task, SubscriptionTaskInterface)
        return path

    def register_with_task(self):
        """Return path to the registration DBus task.

        Either password or activation key based task will be returned,
        based on currently selected authentication method.
        """
        # apply system purpose data, if any, before starting the registration
        # process
        if self.is_system_purpose_set:
            self._apply_syspurpose()

        # decide what task to return based on current authentication method
        if self.authentication_method == AuthenticationMethod.ORG_KEY:
            task = RegisterWithOrganizationKeyTask(self.organization,
                                                   self.activation_keys)
            task.stopped_signal.connect(lambda: self._register_task_callback(task))
            path = self.publish_task(SUBSCRIPTION.namespace, task, SubscriptionTaskInterface)
            return path

        elif self.authentication_method == AuthenticationMethod.LOGIN_PASSWORD:
            task = RegisterWithUsernamePasswordTask(self.red_hat_account_username,
                                                    self.red_hat_account_password)
            task.stopped_signal.connect(lambda: self._register_task_callback(task))
            path = self.publish_task(SUBSCRIPTION.namespace, task, SubscriptionTaskInterface)
            return path
        else:
            raise RuntimeError("Can't authenticate - authentication method not selected!")

    def unregister_with_task(self):
        """Return path to the DBus path used for unregistering the system."""
        task = UnregisterTask()
        task.stopped_signal.connect(lambda: self._unregister_task_callback(task))
        path = self.publish_task(SUBSCRIPTION.namespace, task, SubscriptionTaskInterface)
        return path

    def _assure_yum_repos_folder(self):
        """Due to a RHSM bug, we need to make sure /etc/yum.repos.d exists."""
        # FIXME: drop once RHSM bug is fixed, bug URL:
        #        https://bugzilla.redhat.com/show_bug.cgi?id=1700441
        if not os.path.exists("/etc/yum.repos.d"):
            log.debug("RHSM: yum.repos.d does not exist")
            os.makedirs("/etc/yum.repos.d")
            log.debug("RHSM: yum.repos.d created")
 
    def _restart_rhsm_service(self):
        """Restart the RHSM DBus service.

        There have been a few cases where the RHSM Dbus service will
        not respect changes done via the DBus interface unless it
        is restarted. For this reason we need a way to restart the
        service to make sure the changes we do are respected.
        """
        log.debug("RHSM: restarting rhsm.service")
        util.restart_service("rhsm.service")
        log.debug("RHSM: rhsm.service has been restarted")

    def _set_rhsm_log_level(self, log_level):
        """Set RHSM log level to the desired value.

        :param str log_level: log level inm string form, "INFO" and "DEBUG" are know to work
        """
        log.debug("RHSM: setting RHSM config options")
        self.rhsm_config_proxy.Set("logging.default_log_level", get_variant(Str, log_level), "")
        # There is a bug in RHSM preventing the debug levels from taking effect unless the RHSM
        # service has been restarted:
        # https://bugzilla.redhat.com/show_bug.cgi?id=1777024
        self._restart_rhsm_service()

    def _apply_syspurpose(self):
        """Apply system purpose information to the installation environment.

        If this method is called, then the token transfer installation task will
        make sure to transfer the result, so the system purpose installation task
        does not have to run afterwards.

        For this reason we record if this method has run via the
        _set_is_system_purpose_applied() method.
        """
        log.debug("RHSM: Applying system purpose data from installation kickstart")
        task = SystemPurposeConfigurationTask("/", self.role, self.sla, self.usage, self.addons)
        task.run()
        # set system purpose as applied once the task finishes running
        self._set_is_system_purpose_applied(True)

    # insights

    @property
    def connect_to_insights(self):
        """Indicates if the target system should be connected to red Hat Insights.

        :return: True to connect, False not to connect the target system to Insights
        :rtype: bool
        """
        return self._connect_to_insights

    def set_connect_to_insights(self, connect):
        """Set if the target system should be connected to Red Hat Insights.

        :param bool connect: set to True to connect, set to False not to connect
        """
        self._connect_to_insights = connect
        self.connect_to_insights_changed.emit()
        log.debug("Connect target system to Insights set to: %s", self._connect_to_insights)

    # install time tasks

    def install_with_tasks(self, sysroot):
        # subscription token transfer
        token_transfer_task = TransferSubscriptionTokensTask(sysroot, self.subscription_attached)
        token_transfer_task_path = self.publish_task(SUBSCRIPTION.namespace, token_transfer_task)

        # Insights
        #
        # To connect the target system to Insights we need not only the decision to be indicated via the
        # connect_to_insights property but also have a subscription attached.
        insights_connect_task = ConnectToInsightsTask(sysroot,
                                                      self.subscription_attached,
                                                      self.connect_to_insights)
        insights_connect_task_path = self.publish_task(SUBSCRIPTION.namespace, insights_connect_task)

        # return task list
        return [token_transfer_task_path, insights_connect_task_path]
