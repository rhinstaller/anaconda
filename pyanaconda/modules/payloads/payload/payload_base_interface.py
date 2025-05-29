#
# Base object of all payloads.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABCMeta

from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base.base_template import ModuleInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import PAYLOAD
from pyanaconda.modules.common.containers import (
    PayloadContainer,
    PayloadSourceContainer,
    TaskContainer,
)


@dbus_interface(PAYLOAD.interface_name)
class PayloadBaseInterface(ModuleInterfaceTemplate, metaclass=ABCMeta):
    """Base class for all the payload module interfaces.

    This object contains API shared by all the payloads. Everything in this object has
    to be implemented by a payload to be usable.
    """

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Sources", self.implementation.sources_changed)

    @property
    def Type(self) -> Str:
        """Type of this payload.

        Possible types are values of the payload.base.constants.PayloadType enum

        :return: a string representation of a payload type
        """
        return self.implementation.type.value

    @property
    def SidePayload(self) -> ObjPath:
        """Side payload attached to this payload.

        The side payload is a payload attached to this payload. It can be configured by this
        payload.

        This side payload calls will be automatically queued for some DBus API in Payloads module.
        """
        side_payload = self.implementation.side_payload

        if not side_payload:
            return ""

        return PayloadContainer.to_object_path(side_payload)

    @property
    def DefaultSourceType(self) -> Str:
        """Type of the default source.

        See the SourceType enum for valid values.

        :return: a string representation of a source type
        """
        if self.implementation.default_source_type is None:
            return ""

        return self.implementation.default_source_type.value

    @property
    def SupportedSourceTypes(self) -> List[Str]:
        """Get list of supported source types.

        See the SourceType enum for valid values.

        :return: a list of string representations of source types
        """
        return [val.value for val in self.implementation.supported_source_types]

    @property
    def Sources(self) -> List[ObjPath]:
        """Get list of sources attached to this payload."""
        return PayloadSourceContainer.to_object_path_list(
            self.implementation.sources
        )

    @Sources.setter
    @emits_properties_changed
    def Sources(self, sources: List[ObjPath]):
        """Attach list of sources to this payload.

        Before setting the sources, please make sure the sources are not initialized otherwise
        the SourceSetupError exception will be raised. Payload has to cleanup after itself.

        ..NOTE:
        The SourceSetupError is a reasonable effort to solve the race condition. However,
        there is still a possibility that the task to initialize sources (`SetupSourcesWithTask()`)
        was created with the old list but not run yet. In that case this check will not work and
        the initialization task will run with the old list.

        :raise: IncompatibleSourceError when source is not a supported type
                SourceSetupError when attached sources are initialized
        """
        self.implementation.set_sources(
            PayloadSourceContainer.from_object_path_list(
                sources
            )
        )

    def SetUpSourcesWithTask(self) -> ObjPath:
        """Set up installation sources."""
        return TaskContainer.to_object_path(
            self.implementation.set_up_sources_with_task()
        )

    def TearDownSourcesWithTask(self) -> ObjPath:
        """Tear down installation sources."""
        return TaskContainer.to_object_path(
            self.implementation.tear_down_sources_with_task()
        )
