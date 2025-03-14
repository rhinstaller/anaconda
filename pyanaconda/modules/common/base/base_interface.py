#
# Base interface for Anaconda modules.
#
# Copyright (C) 2017 Red Hat, Inc.
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

from pyanaconda.modules.common.base.base_template import (
    KickstartModuleInterfaceTemplate,
)
from pyanaconda.modules.common.constants.interfaces import KICKSTART_MODULE
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.common.structures.requirement import Requirement


@dbus_interface(KICKSTART_MODULE.interface_name)
class KickstartModuleInterface(KickstartModuleInterfaceTemplate):
    """DBus interface of a kickstart module.

    The implementation is provided by the KickstartModule class.
    """

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Kickstarted", self.implementation.kickstarted_changed)

    @property
    def KickstartCommands(self) -> List[Str]:
        """Return names of kickstart commands handled by module.

        :returns: List of names of kickstart commands handled by module.
        """
        return self.implementation.kickstart_command_names

    @property
    def KickstartSections(self) -> List[Str]:
        """Return names of kickstart sections handled by module.

        :returns: List of names of kickstart sections handled by module.
        """
        return self.implementation.kickstart_section_names

    @property
    def KickstartAddons(self) -> List[Str]:
        """Return names of kickstart addons handled by module.

        :returns: List of names of kickstart addons handled by module.
        """
        return self.implementation.kickstart_addon_names

    @property
    def Kickstarted(self) -> Bool:
        """Was this module set up by the kickstart?

        :return: True if module was set up by the kickstart, otherwise False
        """
        return self.implementation.kickstarted

    @Kickstarted.setter
    @emits_properties_changed
    def Kickstarted(self, kickstarted: Bool):
        """Set the Kickstarted property.

        FIXME: This method should be removed after we move the logic from UI.
        """
        self.implementation.kickstarted = kickstarted

    @emits_properties_changed
    def ReadKickstart(self, kickstart: Str) -> Structure:
        """Read the kickstart string.

        :param kickstart: a kickstart string
        :returns: a structure with a kickstart report
        """
        return KickstartReport.to_structure(
            self.implementation.read_kickstart(kickstart)
        )

    def GenerateKickstart(self) -> Str:
        """Return a kickstart representation of the module

        :return: a kickstart string
        """
        return self.implementation.generate_kickstart()

    def CollectRequirements(self) -> List[Structure]:
        """Return installation requirements of this module.

        :return: a list of requirements
        """
        return Requirement.to_structure_list(self.implementation.collect_requirements())

    def SetLocale(self, locale: Str):
        """Set the locale for the module.

        This function modifies the process environment, which is not thread-safe.
        It should be called before any threads are run.

        We cannot get around setting $LANG. Python's gettext implementation
        differs from C in that consults only the environment for the current
        language and not the data set via setlocale. If we want translations
        from python modules to work, something needs to be set in the
        environment when the language changes.

        Examples: "cs_CZ.UTF-8", "fr_FR"
        """
        self.implementation.set_locale(locale)

    def ConfigureWithTasks(self) -> List[ObjPath]:
        """Configure the runtime environment.

        Note: Addons should use it instead of the setup method.

        :returns: a list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.configure_with_tasks()
        )

    def ConfigureBootloaderWithTasks(self, kernel_versions: List[Str]) -> List[ObjPath]:
        """Configure the bootloader after the payload installation.

        FIXME: This is a temporary workaround. The method might change.

        :param kernel_versions: a list of kernel versions
        :return: list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.configure_bootloader_with_tasks(kernel_versions)
        )

    def InstallWithTasks(self) -> List[ObjPath]:
        """Returns installation tasks of this module.

        Note: Addons should use it instead of the execute method.

        :returns: list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.install_with_tasks()
        )

    def TeardownWithTasks(self) -> List[ObjPath]:
        """Returns teardown tasks for this module.

        :returns: list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.teardown_with_tasks()
        )

    def Quit(self):
        """Shut the module down."""
        self.implementation.stop()
