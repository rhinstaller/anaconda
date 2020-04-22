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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import copy
import warnings

from dasbus.typing import get_native

from pyanaconda.core import util
from pyanaconda.core.signal import Signal
from pyanaconda.core.constants import SECRET_TYPE_HIDDEN, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY, \
    SUBSCRIPTION_REQUEST_VALID_TYPES
from pyanaconda.core.configuration.anaconda import conf

from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest
from pyanaconda.modules.common.structures.secret import get_public_copy
from pyanaconda.core.dbus import DBus

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.constants.objects import RHSM_CONFIG
from pyanaconda.modules.common.containers import TaskContainer

from pyanaconda.modules.subscription import system_purpose
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.installation import ConnectToInsightsTask, \
    SystemPurposeConfigurationTask, RestoreRHSMLogLevelTask, TransferSubscriptionTokensTask
from pyanaconda.modules.subscription.initialization import StartRHSMTask
from pyanaconda.modules.subscription.runtime import SetRHSMConfigurationTask
from pyanaconda.modules.subscription.rhsm_observer import RHSMObserver


from pykickstart.errors import KickstartParseWarning

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class SubscriptionService(KickstartService):
    """The Subscription service."""

    def __init__(self):
        super().__init__()

        # system purpose

        self._valid_roles = []
        self._valid_slas = []
        self._valid_usage_types = []

        self._system_purpose_data = SystemPurposeData()
        self.system_purpose_data_changed = Signal()

        self._load_valid_system_purpose_values()

        self._is_system_purpose_applied = False
        self.is_system_purpose_applied_changed = Signal()

        # subscription request

        self._subscription_request = SubscriptionRequest()
        self.subscription_request_changed = Signal()

        # Insights

        # What are the defaults for Red Hat Insights ?
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

        # subscription status
        self.subscription_attached_changed = Signal()
        self._subscription_attached = False

        # RHSM service startup and access
        self._rhsm_startup_task = StartRHSMTask()
        self._rhsm_observer = RHSMObserver(self._rhsm_startup_task.is_service_available)

        # RHSM config default values cache
        self._rhsm_config_defaults = None

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(SUBSCRIPTION.namespace)
        DBus.publish_object(SUBSCRIPTION.object_path, SubscriptionInterface(self))
        DBus.register_service(SUBSCRIPTION.service_name)

    def run(self):
        """Initiate RHSM service startup before starting the main loop.

        This way RHSM service can startup in parallel without blocking
        startup of the Subscription module.
        """
        self._rhsm_startup_task.start()
        super().run()

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
        system_purpose_data = SystemPurposeData()

        system_purpose_data.role = system_purpose.process_field(
            data.syspurpose.role,
            self.valid_roles,
            "role"
        )

        system_purpose_data.sla = system_purpose.process_field(
            data.syspurpose.sla,
            self.valid_slas,
            "sla"
        )

        system_purpose_data.usage = system_purpose.process_field(
            data.syspurpose.usage,
            self.valid_usage_types,
            "usage"
        )

        if data.syspurpose.addons:
            # As we do not have a list of valid addons available, we just use what was provided
            # by the user in kickstart verbatim.
            system_purpose_data.addons = data.syspurpose.addons

        self.set_system_purpose_data(system_purpose_data)

        # apply system purpose data, if any, so that it is all in place when we start
        # talking to the RHSM service
        if self.system_purpose_data.check_data_available():
            self._apply_syspurpose()

        # subscription request

        subscription_request = SubscriptionRequest()

        # credentials
        if data.rhsm.organization:
            subscription_request.organization = data.rhsm.organization
        if data.rhsm.activation_keys:
            subscription_request.activation_keys.set_secret(data.rhsm.activation_keys)

        # if org id and at least one activation key is set, switch authentication
        # type to ORG & KEY
        if data.rhsm.organization and data.rhsm.activation_keys:
            subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY

        # custom URLs
        if data.rhsm.server_hostname:
            subscription_request.server_hostname = data.rhsm.server_hostname
        if data.rhsm.rhsm_baseurl:
            subscription_request.rhsm_baseurl = data.rhsm.rhsm_baseurl

        # HTTP proxy
        if data.rhsm.proxy:
            # first try to parse the proxy string from kickstart
            try:
                proxy = util.ProxyString(data.rhsm.proxy)
                if proxy.host:
                    # ensure port is an integer and set to -1 if unknown
                    port = int(proxy.port) if proxy.port else -1

                    subscription_request.server_proxy_hostname = proxy.host
                    subscription_request.server_proxy_port = port
                    subscription_request.server_proxy_user = proxy.username
                    subscription_request.server_proxy_password.set_secret(proxy.password)
            except util.ProxyStringError as e:
                # should not be fatal, but definitely logged as error
                message = "Failed to parse proxy for the rhsm command: {}".format(str(e))
                warnings.warn(message, KickstartParseWarning)

        # set the resulting subscription request
        self.set_subscription_request(subscription_request)

        # insights
        self.set_connect_to_insights(bool(data.rhsm.connect_to_insights))

    def setup_kickstart(self, data):
        """Return the kickstart string.

        NOTE: We are not writing out the rhsm command as the input can contain
              sensitive data (activation keys, proxy passwords) that we would have
              to omit from the output kickstart. This in turn would make the rhsm
              command incomplete & would turn the output kickstart invalid as a result.
              For this reason we skip the rhsm command completely in the output
              kickstart.
        """

        # system purpose
        data.syspurpose.role = self.system_purpose_data.role
        data.syspurpose.sla = self.system_purpose_data.sla
        data.syspurpose.usage = self.system_purpose_data.usage
        data.syspurpose.addons = self.system_purpose_data.addons

    # system purpose configuration

    def _load_valid_system_purpose_values(self):
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

    @property
    def valid_roles(self):
        """Return a list of valid roles.

        :return: list of valid roles
        :rtype: list of strings
        """
        return self._valid_roles

    @property
    def valid_slas(self):
        """Return a list of valid SLAs.

        :return: list of valid SLAs
        :rtype: list of strings
        """
        return self._valid_slas

    @property
    def valid_usage_types(self):
        """Return a list of valid usage types.

        :return: list of valid usage types
        :rtype: list of strings
        """
        return self._valid_usage_types

    @property
    def system_purpose_data(self):
        """System purpose data.

        A DBus structure holding information about system purpose,
        such as role, sla, usage and addons.

        :return: system purpose DBus structure
        :rtype: DBusData instance
        """
        return self._system_purpose_data

    def set_system_purpose_data(self, system_purpose_data):
        """Set system purpose data.

        Set the complete DBus structure containing system purpose data.

        :param system_purpose_data: system purpose data structure to be set
        :type system_purpose_data: DBus structure
        """
        self._system_purpose_data = system_purpose_data
        self.system_purpose_data_changed.emit()
        log.debug("System purpose data set to %s.", system_purpose_data)

    @property
    def is_system_purpose_applied(self):
        """Report if system purpose has been applied to the system.

        Note that we don't differentiate between the installation environment
        and the target system, as the token transfer installation task will
        make sure any system purpose configuration file created in the installation
        environment will be transferred to the target system.

        We also need to avoid running system purpose configuration again after
        a successful subscription attempt, as subscription can actually change
        the system purpose attached to the system via system purpose values
        attached to an activation key. If we re-run the system purpose task
        on the installed system, we would basically overwrite these changes.
        """
        return self._is_system_purpose_applied

    def set_is_system_purpose_applied(self, system_purpose_applied):
        """Set if system purpose is applied.

        :param bool system_purpose_applied: True if applied, False otherwise

        NOTE: We keep this as a private method, called by the completed signal of the
              task that applies system purpose information on the system.
        """
        self._is_system_purpose_applied = system_purpose_applied
        self.is_system_purpose_applied_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("System purpose is applied set to: %s", system_purpose_applied)

    def _apply_syspurpose(self):
        """Apply system purpose information to the installation environment.

        If this method is called, then the token transfer installation task will
        make sure to transfer the result, so the system purpose installation task
        does not have to run afterwards.
        For this reason we record if this method has run via the
        set_is_system_purpose_applied() method.
        """
        log.debug("subscription: Applying system purpose data")
        task = SystemPurposeConfigurationTask(sysroot="/",
                                              system_purpose_data=self.system_purpose_data)
        # set system purpose as applied/not applied based on True/False returned by run()
        self.set_is_system_purpose_applied(task.run())

    def set_system_purpose_with_task(self):
        """Set system purpose for the installed system with an installation task.

        :return: a DBus path of an installation task
        """
        task = SystemPurposeConfigurationTask(sysroot=conf.target.system_root,
                                              system_purpose_data=self.system_purpose_data)
        # set system purpose as applied once the task successfully finishes running
        task.succeeded_signal.connect(
            lambda: self.set_is_system_purpose_applied(task.get_result()))
        return task

    # subscription request

    def _validate_subscription_request_type(self, request_type):
        """Check that subscription request is of known type."""
        if request_type not in SUBSCRIPTION_REQUEST_VALID_TYPES:
            raise InvalidValueError(
                "Invalid subscription request type set '{}'".format(request_type)
            )

    @property
    def subscription_request(self):
        """Subscription request.

        A DBus structure holding data to be used to subscribe the system.

        :return: subscription request DBus structure
        :rtype: DBusData instance
        """
        # Return a deep copy of the subscription request that
        # has also been cleared of private data.
        # Thankfully the secret Dbus structures modules
        # has the get_public_copy() method that does just
        # that. It creates a deep copy & clears
        # all SecretData and SecretDataList instances.
        return get_public_copy(self._subscription_request)

    def set_subscription_request(self, subscription_request):
        """Set a subscription request.

        Set the complete DBus structure containing subscription
        request data.

        :param subscription_request: subscription request structure to be set
        :type subscription_request: DBus structure
        """
        self._replace_current_subscription_request(subscription_request)
        self.subscription_request_changed.emit()
        log.debug("A subscription request set: %s", str(self._subscription_request))

    def _replace_current_subscription_request(self, new_request):
        """Replace current subscription request without loosing sensitive data.

        We need to do this to prevent blank SecretData & SecretDataList instances
        from wiping out previously set secret data. The instances will be blank
        every time a SubscriptionRequest that went through get_public_copy() comes
        back with the secret data fields unchanged.

        So what we do is depends on type of the incoming secret data:

        - SECRET_TYPE_NONE - use structure from new request unchanged,
                             clearing previously set data (if any)
        - SECRET_TYPE_HIDDEN - secret data has been set previously and
                               cleared when SubscriptionRequest was sent out;
                               put secret data from current request to the
                               new one to prevent it from being lost
                               (this will also switch the secret data
                                instance to SECRET_TYPE_TEXT so that
                                the Subscription module can read it
                                internally)
        - SECRET_TYPE_TEXT - this is new secret entry, we can keep it as is
        """
        current_request = self._subscription_request

        # Red Hat account password
        if new_request.account_password.type == SECRET_TYPE_HIDDEN:
            new_request.account_password = copy.deepcopy(
                current_request.account_password)

        # activation keys used together with an organization id
        if new_request.activation_keys.type == SECRET_TYPE_HIDDEN:
            new_request.activation_keys = copy.deepcopy(
                current_request.activation_keys)

        # RHSM HTTP proxy password
        if new_request.server_proxy_password.type == SECRET_TYPE_HIDDEN:
            new_request.server_proxy_password = copy.deepcopy(
                    current_request.server_proxy_password)

        # replace current request
        self._subscription_request = new_request

    @property
    def connect_to_insights(self):
        """Indicates if the target system should be connected to Red Hat Insights.

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

    # subscription status

    @property
    def subscription_attached(self):
        """Return True if a subscription has been attached to the system.

        :return: True if a subscription has been attached to the system, False otherwise
        :rtype: bool
        """
        return self._subscription_attached

    def set_subscription_attached(self, system_subscription_attached):
        """Set a subscription has been attached to the system.

        :param bool system_registered: True if subscription has been attached, False otherwise
        """
        self._subscription_attached = system_subscription_attached
        self.subscription_attached_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("Subscription attached set to: %s", system_subscription_attached)

    # tasks

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        Order of execution is important:
        - before transferring subscription tokens we need to restore
          the INFO log level in rhsm.conf or else target system will
          end up with RHSM logging in DEBUG mode
        - transfer subscription tokens
        - connect to insights, this can run only once subscription
          tokens are in place on the target system or else it would
          fail as Insights client needs the subscription tokens to
          authenticate to the Red Hat Insights online service

        :returns: list of installation tasks
        """
        return [
            RestoreRHSMLogLevelTask(
                rhsm_config_proxy=self.rhsm_observer.get_proxy(RHSM_CONFIG)
            ),
            TransferSubscriptionTokensTask(
                sysroot=conf.target.system_root,
                transfer_subscription_tokens=self.subscription_attached
            ),
            ConnectToInsightsTask(
                sysroot=conf.target.system_root,
                subscription_attached=self.subscription_attached,
                connect_to_insights=self.connect_to_insights
            )
        ]

    # RHSM DBus API access

    @property
    def rhsm_observer(self):
        """Provide access to the RHSM DBus service observer.

        This observer handles various peculiarities of the
        RHSM DBus API startup and should be used as the
        only access point to the RHSM Dbus API.

        If you need to RHSM DBus API object, just call the
        get_proxy() method of the observer with object
        identifier.

        :return: RHSM DBus API observer
        :rtype: RHSMObserver instance
        """
        return self._rhsm_observer

    def get_rhsm_config_defaults(self):
        """Return RHSM config default values.

        We need to have these available in case the user decides
        to return to default values from a custom value at
        runtime.

        This method is lazy evaluated, the first call it fetches
        the full config dict from RHSM and subsequent calls are
        then served from cache.

        Due to this it is important not to set RHSM configuration
        values before first calling this method to populate the cache
        or else the method might return non-default (Anaconda overwritten)
        data.

        :return : dictionary of default RHSM configuration values
        :rtype: dict
        """
        if self._rhsm_config_defaults is None:
            # config defaults cache not yet populated, do it now
            proxy = self.rhsm_observer.get_proxy(RHSM_CONFIG)
            # turn the variant into a dict with get_native()
            self._rhsm_config_defaults = get_native(proxy.GetAll(""))
        return self._rhsm_config_defaults

    def set_rhsm_config_with_task(self):
        """Set RHSM config values based on current subscription request.

        :return: a DBus path of an installation task
        """
        # NOTE: we access self._subscription_request directly
        #       to avoid the sensitive data clearing happening
        #       in the subscription_request property getter
        rhsm_config_proxy = self.rhsm_observer.get_proxy(RHSM_CONFIG)
        task = SetRHSMConfigurationTask(rhsm_config_proxy=rhsm_config_proxy,
                                        rhsm_config_defaults=self.get_rhsm_config_defaults(),
                                        subscription_request=self._subscription_request)
        return task
