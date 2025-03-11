#
# DBus interface for the subscription module.
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
from dasbus.server.interface import dbus_class, dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.subscription import (
    OrganizationData,
    SubscriptionRequest,
    SystemPurposeData,
)
from pyanaconda.modules.common.task import TaskInterface


@dbus_class
class RetrieveOrganizationsTaskInterface(TaskInterface):
    """The interface for a organization data parsing task.

    Such a task returns a list of organization data objects.
    """
    @staticmethod
    def convert_result(value) -> Variant:
        """Convert the list of org data DBus structs.

        Convert list of org data DBus structs to variant.
        :param value: a validation report
        :return: a variant with the structure
        """
        return get_variant(List[Structure], OrganizationData.to_structure_list(value))


@dbus_interface(SUBSCRIPTION.interface_name)
class SubscriptionInterface(KickstartModuleInterface):
    """DBus interface for the Subscription service."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("SystemPurposeData",
                            self.implementation.system_purpose_data_changed)
        self.watch_property("SubscriptionRequest",
                            self.implementation.subscription_request_changed)
        self.watch_property("InsightsEnabled",
                            self.implementation.connect_to_insights_changed)
        self.watch_property("IsRegistered",
                            self.implementation.registered_changed)
        self.watch_property("IsRegisteredToSatellite",
                            self.implementation.registered_to_satellite_changed)
        self.watch_property("IsSimpleContentAccessEnabled",
                            self.implementation.simple_content_access_enabled_changed)
        self.watch_property("IsSubscriptionAttached",
                            self.implementation.subscription_attached_changed)

    def GetValidRoles(self) -> List[Str]:
        """Return all valid system purpose roles.

        These are OS release specific, but could look like this:

        "Red Hat Enterprise Linux Server"
        "Red Hat Enterprise Linux Workstation"
        "Red Hat Enterprise Linux Compute Node"
        """
        return self.implementation.valid_roles

    def GetValidSLAs(self) -> List[Str]:
        """Return all valid system purpose SLAs.

        These are OS release specific, but could look like this:

        "Premium"
        "Standard"
        "Self-Support"
        """
        return self.implementation.valid_slas

    def GetValidUsageTypes(self) -> List[Str]:
        """List all valid system purpose usage types.

        These are OS release specific, but could look like this:

        "Production",
        "Development/Test",
        "Disaster Recovery"
        """
        return self.implementation.valid_usage_types

    @property
    def SystemPurposeData(self) -> Structure:
        """Return DBus structure holding current system purpose data."""
        return SystemPurposeData.to_structure(self.implementation.system_purpose_data)

    @SystemPurposeData.setter
    @emits_properties_changed
    def SystemPurposeData(self, system_purpose_data: Structure):
        """Set a new DBus structure holding system purpose data.

        :param system_purpose_data: DBus structure corresponding to SystemPurposeData
        """
        converted_data = SystemPurposeData.from_structure(system_purpose_data)
        self.implementation.set_system_purpose_data(converted_data)

    def SetSystemPurposeWithTask(self) -> ObjPath:
        """Set system purpose for the installed system with an installation task.

        :return: a DBus path of an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.set_system_purpose_with_task()
        )

    @property
    def SubscriptionRequest(self) -> Structure:
        """Return DBus structure holding current subscription request.

        Subscription request holds data necessary for a successful subscription attempt.
        """
        return SubscriptionRequest.to_structure(self.implementation.subscription_request)

    @SubscriptionRequest.setter
    @emits_properties_changed
    def SubscriptionRequest(self, subscription_request: Structure):
        """Set a new DBus structure holding subscription request data.

        :param subscription_request: DBus structure corresponding to SubscriptionRequest
        """
        converted_data = SubscriptionRequest.from_structure(subscription_request)
        self.implementation.set_subscription_request(converted_data)

    @property
    def InsightsEnabled(self) -> Int:
        """Connect the target system to Red Hat Insights."""
        return self.implementation.connect_to_insights

    @InsightsEnabled.setter
    @emits_properties_changed
    def InsightsEnabled(self, connect_to_insights: Bool):
        """Set if the target system should be connected to Red Hat Insights.

        :param bool connect_to_insights: True to connect, False not to connect
        """
        self.implementation.set_connect_to_insights(connect_to_insights)

    @property
    def IsRegistered(self) -> Bool:
        """Report if the system is registered."""
        return self.implementation.registered

    @property
    def IsRegisteredToSatellite(self) -> Bool:
        """Report if the system is registered to a Satellite instance."""
        return self.implementation.registered_to_satellite

    @property
    def IsSimpleContentAccessEnabled(self) -> Bool:
        """Report if Simple Content Access is enabled."""
        return self.implementation.simple_content_access_enabled

    @property
    def IsSubscriptionAttached(self) -> Bool:
        """Report if an entitlement has been successfully attached."""
        return self.implementation.subscription_attached

    def SetRHSMConfigWithTask(self) -> ObjPath:
        """Set RHSM configuration with a runtime DBus task.

        :return: a DBus path of an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.set_rhsm_config_with_task()
        )

    def UnregisterWithTask(self) -> ObjPath:
        """Unregister using a runtime DBus task.

        :return: a DBus path of an installation task
        """
        return TaskContainer.to_object_path(
            self.implementation.unregister_with_task()
        )

    def RegisterAndSubscribeWithTask(self) -> ObjPath:
        """Register and subscribe with a runtime DBus task.

        :return: a DBus path of a runtime task
        """
        return TaskContainer.to_object_path(
            self.implementation.register_and_subscribe_with_task()
        )

    def RetrieveOrganizationsWithTask(self) -> ObjPath:
        """Get organization data using a runtime DBus task.

        :return: a DBus path of a runtime task
        """
        return TaskContainer.to_object_path(
            self.implementation.retrieve_organizations_with_task()
        )
