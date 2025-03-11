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

# pylint: skip-file
# FIXME: https://github.com/pylint-dev/astroid/issues/2391
# There is a known issue with astroid, remove this when it's fixed upstream.

import copy
import warnings

from dasbus.typing import get_native
from pykickstart.errors import KickstartParseWarning

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    SECRET_TYPE_HIDDEN,
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
)
from pyanaconda.core.dbus import DBus
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.objects import (
    RHSM_CONFIG,
    RHSM_REGISTER_SERVER,
    RHSM_SYSPURPOSE,
)
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.structures.secret import get_public_copy
from pyanaconda.modules.common.structures.subscription import (
    SubscriptionRequest,
    SystemPurposeData,
)
from pyanaconda.modules.subscription import system_purpose
from pyanaconda.modules.subscription.initialization import StartRHSMTask
from pyanaconda.modules.subscription.installation import (
    ConnectToInsightsTask,
    ProvisionTargetSystemForSatelliteTask,
    RestoreRHSMDefaultsTask,
    TransferSubscriptionTokensTask,
)
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification
from pyanaconda.modules.subscription.rhsm_observer import RHSMObserver
from pyanaconda.modules.subscription.runtime import (
    RegisterAndSubscribeTask,
    RetrieveOrganizationsTask,
    SetRHSMConfigurationTask,
    SystemPurposeConfigurationTask,
    UnregisterTask,
)
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.utils import flatten_rhsm_nested_dict

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

        # Satellite
        self._satellite_provisioning_script = None
        self.registered_to_satellite_changed = Signal()
        self._registered_to_satellite = False
        self._rhsm_conf_before_satellite_provisioning = {}

        # registration status
        self.registered_changed = Signal()
        self._registered = False

        # simple content access
        self.simple_content_access_enabled_changed = Signal()
        self._sca_enabled = False

        # subscription status
        self.subscription_attached_changed = Signal()
        self._subscription_attached = False

        # RHSM service startup and access
        self._rhsm_startup_task = StartRHSMTask(verify_ssl=conf.payload.verify_ssl)
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
                proxy = ProxyString(data.rhsm.proxy)
                if proxy.host:
                    # ensure port is an integer and set to -1 if unknown
                    port = int(proxy.port) if proxy.port else -1

                    subscription_request.server_proxy_hostname = proxy.host
                    subscription_request.server_proxy_port = port

                    # ensure no username translates to the expected ""
                    # instead of the None returned by the ProxyString class
                    subscription_request.server_proxy_user = proxy.username or ""
                    subscription_request.server_proxy_password.set_secret(proxy.password)
            except ProxyStringError as e:
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

    def _apply_syspurpose(self):
        """Apply system purpose information to the installation environment."""
        log.debug("subscription: Applying system purpose data")
        task = self.set_system_purpose_with_task()
        task.run()

    def set_system_purpose_with_task(self):
        """Set system purpose for the installed system with an installation task.
        :return: a DBus path of an installation task
        """
        rhsm_syspurpose_proxy = self.rhsm_observer.get_proxy(RHSM_SYSPURPOSE)
        task = SystemPurposeConfigurationTask(
            rhsm_syspurpose_proxy=rhsm_syspurpose_proxy,
            system_purpose_data=self.system_purpose_data
        )
        return task

    # subscription request

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

    # registration status

    @property
    def registered(self):
        """Return True if the system has been registered.

        NOTE: Together with the subscription_attached property
              the registered property can be used to detect that
              the system is registered but has not subscription
              attached. This is generally a sign something went
              wrong, usually when trying to attach subscription.

        :return: True if the system has been registered, False otherwise
        :rtype: bool
        """
        return self._registered

    def set_registered(self, system_registered):
        """Set if the system is registered.

        :param bool system_registered: True if system has been registered, False otherwise
        """
        self._registered = system_registered
        self.registered_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("System registered set to: %s", system_registered)

    @property
    def registered_to_satellite(self):
        """Return True if the system has been registered to a Satellite instance.

        :return: True if the system has been registered to Satellite, False otherwise
        :rtype: bool
        """
        return self._registered_to_satellite

    def set_registered_to_satellite(self, system_registered_to_satellite):
        """Set if the system is registered to a Satellite instance.

        If we are not registered to a Satellite instance it means we are registered
        to Hosted Candlepin.

        :param bool system_registered_to_satellite: True if system has been registered
                                                    to Satellite, False otherwise
        """
        self._registered_to_satellite = system_registered_to_satellite
        self.registered_to_satellite_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("System registered to Satellite set to: %s", system_registered_to_satellite)

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

    # simple content access status
    @property
    def simple_content_access_enabled(self):
        """Return True if the system has been registered with SCA enabled.

        :return: True if the system has been registered in SCA mode, False otherwise
        :rtype: bool
        """
        return self._sca_enabled

    def set_simple_content_access_enabled(self, sca_enabled):
        """Set if Simple Content Access is enabled.

        :param bool sca_enabled: True if SCA is enabled, False otherwise
        """
        self._sca_enabled = sca_enabled
        self.simple_content_access_enabled_changed.emit()
        # as there is no public setter in the DBus API, we need to emit
        # the properties changed signal here manually
        self.module_properties_changed.emit()
        log.debug("Simple Content Access enabled set to: %s", sca_enabled)

    # tasks

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        Order of execution is important:
        - before transferring subscription tokens we need to restore
          the INFO log level in rhsm.conf or else target system will
          end up with RHSM logging in DEBUG mode
        - transfer subscription tokens
        - apply Satellite provisioning on the target system,
          in case we are registered to Satellite
        - connect to insights, this can run only once subscription
          tokens are in place on the target system or else it would
          fail as Insights client needs the subscription tokens to
          authenticate to the Red Hat Insights online service

        :returns: list of installation tasks
        """
        return [
            RestoreRHSMDefaultsTask(
                rhsm_config_proxy=self.rhsm_observer.get_proxy(RHSM_CONFIG)
            ),
            TransferSubscriptionTokensTask(
                sysroot=conf.target.system_root,
                transfer_subscription_tokens=self.subscription_attached
            ),
            ProvisionTargetSystemForSatelliteTask(
                provisioning_script=self._satellite_provisioning_script,
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

        NOTE: While RHSM GetAll() DBus call returns a nested dictionary,
              we turn it into a flat key/value dict, in the same format SetAll()
              uses.

        :return : dictionary of default RHSM configuration values
        :rtype: dict
        """
        if self._rhsm_config_defaults is None:
            # config defaults cache not yet populated, do it now
            proxy = self.rhsm_observer.get_proxy(RHSM_CONFIG)
            # turn the variant into a dict with get_native()
            nested_dict = get_native(proxy.GetAll(""))
            # flatten the nested dict
            flat_dict = flatten_rhsm_nested_dict(nested_dict)
            self._rhsm_config_defaults = flat_dict
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

    def unregister_with_task(self):
        """Unregister the system.

        :return: a DBus path of an installation task
        """
        # the configuration backup is already flattened by the task that fetched it,
        # we can directly feed it to SetAll()
        task = UnregisterTask(rhsm_observer=self.rhsm_observer,
                              registered_to_satellite=self.registered_to_satellite,
                              rhsm_configuration=self._rhsm_conf_before_satellite_provisioning)
        # apply state changes on success
        task.succeeded_signal.connect(self._system_unregistered_callback)
        return task

    def _system_unregistered_callback(self):
        """Callback function run on success of the unregistration task.

        The general aim is to set the various variables to reflect that
        the installation environment is no longer registered.
        """
        # we are no longer registered and subscribed
        self.set_registered(False)
        self.set_subscription_attached(False)
        # clear the Satellite registration status as well
        self.set_registered_to_satellite(False)
        # don't forget to also clear the Satellite provisioning
        # script, or else it will be run by the target system
        # provisioning task
        self._set_satellite_provisioning_script(None)
        # also when we are no longer registered then we are are
        # thus no longer in Simple Content Access mode
        self.set_simple_content_access_enabled(False)

    def _set_system_subscription_data(self, system_subscription_data):
        """A helper method invoked in ParseSubscriptionDataTask completed signal.

        :param system_subscription_data: a named tuple holding attached subscriptions
                                         and final system purpose data
        """
        self.set_system_purpose_data(system_subscription_data.system_purpose_data)

    def _set_satellite_provisioning_script(self, provisioning_script):
        """Set satellite provisioning script we just downloaded.

        :param str provisioning_script: Satellite provisioning script in string form
        """
        self._satellite_provisioning_script = provisioning_script

    def _set_pre_satellite_rhsm_conf_snapshot(self, config_data):
        """A helper method for BackupRHSMConfBeforeSatelliteProvisioningTask completed signal.

        :param config_data: RHSM config content before Satellite provisioning
        """
        self._rhsm_conf_before_satellite_provisioning = config_data

    def register_and_subscribe_with_task(self):
        """Register and subscribe the installation environment.

        Also handle Satellite provisioning and attached subscription parsing.

        :return: a DBus path of a runtime task
        """

        task = RegisterAndSubscribeTask(
            rhsm_observer=self.rhsm_observer,
            subscription_request=self._subscription_request,
            system_purpose_data=self.system_purpose_data,
            registered_callback=self.set_registered,
            registered_to_satellite_callback=self.set_registered_to_satellite,
            simple_content_access_callback=self.set_simple_content_access_enabled,
            subscription_attached_callback=self.set_subscription_attached,
            subscription_data_callback=self._set_system_subscription_data,
            satellite_script_callback=self._set_satellite_provisioning_script,
            config_backup_callback=self._set_pre_satellite_rhsm_conf_snapshot
        )

        return task

    def retrieve_organizations_with_task(self):
        """Retrieve organization data with task.

        Parse data about organizations the currently used Red Hat account is a member of.
        :return: a runtime task
        """
        # NOTE: we access self._subscription_request directly
        #       to avoid the sensitive data clearing happening
        #       in the subscription_request property getter
        username = self._subscription_request.account_username
        password = self._subscription_request.account_password.value
        register_server_proxy = self.rhsm_observer.get_proxy(RHSM_REGISTER_SERVER)
        task = RetrieveOrganizationsTask(rhsm_register_server_proxy=register_server_proxy,
                                         username=username,
                                         password=password)
        return task

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []
        # check if we need the insights-client package, which is needed to connect the
        # target system to Red Hat Insights
        if self.subscription_attached and self.connect_to_insights:
            # establishing a connection to Red Hat Insights has been requested
            # and we need the insights-client package to be present in the
            # target system chroot for that
            requirements.append(
                Requirement.for_package(
                    "insights-client",
                    reason="Needed to connect the target system to Red Hat Insights."
                )
            )
        return requirements
