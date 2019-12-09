#
# DBus interface for the subscription module.
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
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.subscription.constants import AuthenticationMethod
from pyanaconda.dbus.interface import dbus_interface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

@dbus_interface(SUBSCRIPTION.interface_name)
class SubscriptionInterface(KickstartModuleInterface):
    """DBus interface for Subscription module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Role", self.implementation.role_changed)
        self.watch_property("SLA", self.implementation.sla_changed)
        self.watch_property("Usage", self.implementation.usage_changed)
        self.watch_property("Addons", self.implementation.addons_changed)
        self.watch_property("IsSubscriptionAttached", self.implementation.subscription_attached_changed)
        self.watch_property("Organization", self.implementation.organization_changed)
        self.watch_property("IsActivationKeySet", self.implementation.activation_keys_changed)
        self.watch_property("AccountUsername", self.implementation.red_hat_account_username_changed)
        self.watch_property("IsAccountPasswordSet", self.implementation.red_hat_account_password_changed)
        self.watch_property("ServerHostname", self.implementation.server_hostname_changed)
        self.watch_property("RHSMBaseurl", self.implementation.rhsm_baseurl_changed)
        self.watch_property("InsightsEnabled", self.implementation.connect_to_insights_changed)
        self.watch_property("ServerProxyHostname", self.implementation.server_proxy_configuration_changed)
        self.watch_property("ServerProxyPort", self.implementation.server_proxy_configuration_changed)
        self.watch_property("ServerProxyUser", self.implementation.server_proxy_configuration_changed)
        self.watch_property("ServerProxyPasswordSet", self.implementation.server_proxy_configuration_changed)
        self.watch_property("AttachedSubscriptions", self.implementation.attached_subscriptions_changed)

        # the SystemPurposeWillBeSet property depends on the value of
        # all other system purpose properties
        self.watch_property("IsSystemPurposeSet", self.implementation.is_system_purpose_set_changed)
        self.watch_property("IsSystemPurposeApplied", self.implementation.is_system_purpose_applied_changed)

    # system purpose

    @property
    def ValidRoles(self) -> List[Str]:
        """Return all valid roles."""
        return self.implementation.valid_roles

    @property
    def Role(self) -> Str:
        """Role for system subscription purposes."""
        return self.implementation.role

    @emits_properties_changed
    def SetRole(self, role: Str):
        """Set the intended role.

        Sets the role intent for subscription purposes.

        This setting is optional.

        :param str role: a role string
        """
        self.implementation.set_role(role)

    @property
    def ValidSLAs(self) -> List[Str]:
        """Return all valid SLAs."""
        return self.implementation.valid_slas

    @property
    def SLA(self) -> Str:
        """SLA for system subscription purposes."""
        return self.implementation.sla

    @emits_properties_changed
    def SetSLA(self, sla: Str):
        """Set the intended SLA.

        Sets the SLA intent for subscription purposes.

        This setting is optional.

        :param str sla: a SLA string
        """
        self.implementation.set_sla(sla)

    @property
    def ValidUsageTypes(self) -> List[Str]:
        """List all valid usage types."""
        return self.implementation.valid_usage_types

    @property
    def Usage(self) -> Str:
        """Usage for system subscription purposes."""
        return self.implementation.usage

    @emits_properties_changed
    def SetUsage(self, usage: Str):
        """Set the intended usage.

        Sets the usage intent for subscription purposes.

        This setting is optional.

        :param str usage: a usage string
        """
        self.implementation.set_usage(usage)

    @property
    def Addons(self) -> List[Str]:
        """Addons for system subscription purposes."""
        return self.implementation.addons

    @emits_properties_changed
    def SetAddons(self, addons: List[Str]):
        """Set the intended addons (additional layered products and features).

        This setting is optional.

        :param addons: a list of strings, one per layered product/feature
        :type addons: list of strings
        """
        self.implementation.set_addons(addons)

    @property
    def IsSystemPurposeSet(self) -> Bool:
        """Report if at least one system purpose value is set.

        This is basically a shortcut so that the DBUS API users don't
        have to query Role, Sla, Usage & Addons every time they want
        to check if at least one system purpose value is set.
        """
        return self.implementation.is_system_purpose_set

    @property
    def IsSystemPurposeApplied(self) -> Bool:
        """Report if system purpose data has been applied.

        We don't differentiate between that installation environment and the target system in this
        case as we will make sure the system purpose data will always end up on the target system
        if requested by the user, regardless of where it is initially set or requested.
        """
        return self.implementation.is_system_purpose_applied

    def SetSystemPurposeWithTask(self, sysroot: Str) -> ObjPath:
        """Set system purpose for the installed system with an installation task.

        FIXME: This is just a temporary method.

        :return: a DBus path of an installation task
        """
        return self.implementation.set_system_purpose_with_task(sysroot)

    # subscription

    @property
    def IsRegistered(self) -> Bool:
        """Report if the system has been registered."""
        return self.implementation.registered

    @property
    def IsSubscriptionAttached(self) -> Bool:
        """Report if an entilement has been successfully attached."""
        return self.implementation.subscription_attached

    @property
    def AttachedSubscriptions(self) -> List[Dict[Str, Str]]:
        """Return list of attached subscriptions (if any)."""
        # we need to turn the AttachedSubscription instances
        # to dictionaries before transfering them over DBus
        attached_subscriptions = []
        for subscription in self.implementation.attached_subscriptions:
            attached_subscriptions.append(subscription.as_dict())
        return attached_subscriptions

    @property
    def Organization(self) -> Str:
        """Organization name for subscription purposes."""
        return self.implementation.organization

    @emits_properties_changed
    def SetOrganization(self, organization: Str):
        """Set organization name.

        :param str organization: organization name
        """
        self.implementation.set_organization(organization)

    @property
    def IsActivationKeySet(self) -> Bool:
        """Report if at least one activation key has been set."""
        return bool(self.implementation.activation_keys)

    @emits_properties_changed
    def SetActivationKeys(self, activation_keys: List[Str]):
        """Set activation keys for subscription purposes.

        For a successfull subscription at least one activation
        key is needed.

        :param activation_keys: activation keys
        :type activation_keys: list of str
        """
        self.implementation.set_activation_keys(activation_keys)

    @property
    def AccountUsername(self) -> Str:
        """Red Hat account name for subscription purposes."""
        return self.implementation.red_hat_account_username

    @emits_properties_changed
    def SetAccountUsername(self, account_username: Str):
        """Set Red Hat account name.

        :param str account_name: Red Hat account name
        """
        self.implementation.set_red_hat_account_username(account_username)

    @property
    def IsAccountPasswordSet(self) -> Bool:
        """Report if Red Hat account password has been set."""
        return bool(self.implementation.red_hat_account_password)

    @emits_properties_changed
    def SetAccountPassword(self, password: Str):
        """Set Red Hat account password.

        :param str password: a Red Hat account password
        """
        self.implementation.set_red_hat_account_password(password)

    @property
    def AuthenticationMethod(self) -> Int:
        """Authentication method for subscription purposes."""
        return int(self.implementation.authentication_method)

    @emits_properties_changed
    def SetAuthenticationMethod(self, method: Int):
        """Set authetication method for subscription purposes."""
        self.implementation.set_authentication_method(AuthenticationMethod(method))

    @property
    def ServerProxyHostname(self) -> Str:
        """RHSM HTTP proxy hostname."""
        return self.implementation.server_proxy_hostname

    @property
    def ServerProxyPort(self) -> Int:
        """RHSM HTTP proxy port.

        -1 means port has not been set.
        """
        return self.implementation.server_proxy_port

    @property
    def ServerProxyUser(self) -> Str:
        """RHSM HTTP proxy access username."""
        return self.implementation.server_proxy_user

    @property
    def ServerProxyPasswordSet(self) -> Bool:
        """Report if RHSM HTTP proxy access password has been set."""
        return self.implementation.server_proxy_password_set

    @emits_properties_changed
    def SetServerProxy(self, hostname : Str, port : Int, username : Str, password : Str):
        """Set RHSM HTTP proxy configuration.

        :param str hostname: RHSM HTTP proxy hostname
        :param int post: RHSM HTTP proxy port (set to -1 to clear)
        :param str username: RHSM HTTP proxy access username
        :param str password: RHSM HTTP proxy access password
        """
        self.implementation.set_server_proxy(hostname, port, username, password)

    @property
    def ServerHostname(self) -> Str:
        """Override Red Hat subscription server hostname.

        Empty string means default server hostname will be used
        by Subscription Manager.
        """
        return self.implementation.server_hostname

    @emits_properties_changed
    def SetServerHostname(self, hostname: Str):
        """Set Red Hat subscription server hostname.

        Setting "" will restore initial value before
        it was first overriden using this method.

        :param str hostname: Red Hat subscription server hostname
        """
        self.implementation.set_server_hostname(hostname)

    @property
    def RHSMBaseurl(self) -> Str:
        """Red Hat CDN baseurl.

        Empty string means default content baseurl will be used
        by Subscription Manager.
        """
        return self.implementation.rhsm_baseurl

    @emits_properties_changed
    def SetRHSMBaseurl(self, baseurl: Str):
        """Red Hat CDN baseurl.

        Setting "" will restore initial value before
        it was first overriden using this method.

        :param str url: Red Hat subscription service URL
        """
        self.implementation.set_rhsm_baseurl(baseurl)

    @property
    def InsightsEnabled(self) -> Int:
        """Connect the target system to Red Hat Insights."""
        return self.implementation.connect_to_insights

    @emits_properties_changed
    def SetInsightsEnabled(self, connect_to_insights : Bool):
        """Set if the target system should be connected to Red Hat Insights.

        :param bool connect_to_insights: True to connect, False not to connect
        """
        self.implementation.set_connect_to_insights(connect_to_insights)

    def RegisterWithTask(self) -> ObjPath:
        """Register with an installation task.

        :return: a DBus path of an installation task
        """
        return self.implementation.register_with_task()

    def UnregisterWithTask(self) -> ObjPath:
        """Unregister with an installation task.

        :return: a DBus path of an installation task
        """
        return self.implementation.unregister_with_task()

    def AttachWithTask(self) -> ObjPath:
        """Attach subscription with an installation task.

        FIXME: This is just a temporary method.

        :return: a DBus path of an installation task
        """
        return self.implementation.attach_subscription_with_task()
