#
# DBus interface for packaging.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.containers import (
    PayloadContainer,
    PayloadSourceContainer,
    TaskContainer,
)
from pyanaconda.modules.payloads.constants import PayloadType, SourceType


@dbus_interface(PAYLOADS.interface_name)
class PayloadsInterface(KickstartModuleInterface):
    """DBus interface for Payload module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("CreatedPayloads", self.implementation.created_payloads_changed)
        self.watch_property("ActivePayload", self.implementation.active_payload_changed)

    @emits_properties_changed
    def CreatePayload(self, payload_type: Str) -> ObjPath:
        """Create payload and publish it on DBus.

        payload_type could contain these values:
         - DNF
         - LIVE_OS
         - LIVE_IMAGE
        """
        return PayloadContainer.to_object_path(
            self.implementation.create_payload(PayloadType(payload_type))
        )

    @property
    def CreatedPayloads(self) -> List[ObjPath]:
        """List of all created payload modules.

        :return: a list of DBus paths
        """
        return PayloadContainer.to_object_path_list(
            self.implementation.created_payloads
        )

    @emits_properties_changed
    def ActivatePayload(self, payload: ObjPath):
        """Activate the payload.

        :param payload: a path to a payload
        """
        self.implementation.activate_payload(
            PayloadContainer.from_object_path(payload)
        )

    @property
    def ActivePayload(self) -> Str:
        """The active payload.

        :return: a DBus path or an empty string
        """
        payload = self.implementation.active_payload

        if not payload:
            return ""

        return PayloadContainer.to_object_path(payload)

    def CreateSource(self, source_type: Str) -> ObjPath:
        """Create payload source and publish it on DBus.

        source_type could contain these values:
         - LIVE_OS_IMAGE
        """
        return PayloadSourceContainer.to_object_path(
            self.implementation.create_source(SourceType(source_type))
        )

    def IsNetworkRequired(self) -> Bool:
        """Do the sources require a network?

        :return: True or False
        """
        return self.implementation.is_network_required()

    def CalculateRequiredSpace(self) -> UInt64:
        """Calculate space required for the installation.

        Calculate required space for the main payload and the side payload if exists.

        :return: required size in bytes
        :rtype: int
        """
        return self.implementation.calculate_required_space()

    def GetKernelVersionList(self) -> List[Str]:
        """Get the kernel versions list.

        The kernel version list doesn't have to be available
        before the payload installation.

        :return: a list of kernel versions
        :raises UnavailableValueError: if the list is not available
        """
        return self.implementation.get_kernel_version_list()

    # Update documentation of this method from parent.
    def InstallWithTasks(self) -> List[ObjPath]:  # pylint: disable=useless-parent-delegation
        """Returns installation tasks of this module.

        Concatenate tasks of the main payload together with side payload of that payload.

        :returns: list of object paths of installation tasks
        """
        return super().InstallWithTasks()

    def PostInstallWithTasks(self) -> List[ObjPath]:
        """Return a list of post-installation tasks.

        Concatenate tasks of the main payload together with side payload of that payload.

        :return: a list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.post_install_with_tasks()
        )

    # Update documentation of this method from parent.
    def TeardownWithTasks(self) -> List[ObjPath]:  # pylint: disable=useless-parent-delegation
        """Returns teardown tasks for this module.

        Concatenate tasks of the main payload together with side payload of that payload.

        :returns: list of object paths of installation tasks
        """
        return super().TeardownWithTasks()
