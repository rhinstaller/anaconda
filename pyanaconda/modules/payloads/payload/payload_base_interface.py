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
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base.base_template import ModuleInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import PAYLOAD
from pyanaconda.modules.common.containers import PayloadSourceContainer, TaskContainer


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
        """Get type of this payload.

        Possible types are values of the payload.base.constants.PayloadType enum
        """
        return self.implementation.type.value

    @property
    def SupportedSourceTypes(self) -> List[Str]:
        """Get list of supported source types."""
        return [val.value for val in self.implementation.supported_source_types]

    @property
    def Sources(self) -> List[ObjPath]:
        """Get list of sources attached to this payload."""
        return PayloadSourceContainer.to_object_path_list(
            self.implementation.sources
        )

    def SetSources(self, sources: List[ObjPath]):
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

    def IsNetworkRequired(self) -> Bool:
        """Do the sources require a network?

        :return: True or False
        """
        return self.implementation.is_network_required()

    def CalculateRequiredSpace(self) -> UInt64:
        """Calculate space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return self.implementation.calculate_required_space()

    def PreInstallWithTasks(self) -> List[ObjPath]:
        """Execute preparation steps.

        FIXME: Temporary -- installation methods will be provided only by the main service
        """
        return TaskContainer.to_object_path_list(
            self.implementation.pre_install_with_tasks()
        )

    def InstallWithTasks(self) -> List[ObjPath]:
        """Install the payload.

        FIXME: Temporary -- installation methods will be provided only by the main service
        """
        return TaskContainer.to_object_path_list(
            self.implementation.install_with_tasks()
        )

    def PostInstallWithTasks(self) -> List[ObjPath]:
        """Execute post installation steps.

        FIXME: Temporary -- installation methods will be provided only by the main service
        """
        return TaskContainer.to_object_path_list(
            self.implementation.post_install_with_tasks()
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
