#
# base_interface.py
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pykickstart.errors import KickstartError

from pyanaconda.modules.common.constants.interfaces import KICKSTART_MODULE
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.template import AdvancedInterfaceTemplate
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(KICKSTART_MODULE.interface_name)
class KickstartModuleInterface(AdvancedInterfaceTemplate):
    """DBus interface of a kickstart module.

    The implementation is provided by the KickstartModule class.
    """

    def connect_signals(self):
        """Connect the signals."""
        self.implementation.module_properties_changed.connect(self.flush_changes)
        self.implementation.kickstarted_changed.connect(self.changed("Kickstarted"))

    @property
    def AvailableTasks(self) -> List[Tuple[Str, Str]]:
        """Return DBus object paths for tasks available for this module.

        :returns: List of tuples (Name, DBus object path) for all Tasks.
                  See pyanaconda.task.Task for Task API.
        """
        result = []

        for task in self.implementation.published_tasks:
            result.append((task.Name, task.object_path))

        return result

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

    def SetKickstarted(self, kickstarted: Bool):
        """Set the Kickstarted property.

        FIXME: This method should be removed after we move the logic from UI.
        """
        self.implementation.kickstarted = kickstarted

    @emits_properties_changed
    def ReadKickstart(self, kickstart: Str) -> Dict[Str, Variant]:
        """Read the kickstart string.

        :param kickstart: a kickstart string
        :returns: a dictionary with a result
        """
        try:
            self.implementation.read_kickstart(kickstart)
        except KickstartError as e:
            return {
                "success": get_variant(Bool, False),
                "error_message": get_variant(Str, str(e.message)),
                "line_number": get_variant(Int, e.lineno)
            }

        return {"success": get_variant(Bool, True)}

    def GenerateKickstart(self) -> Str:
        """Return a kickstart representation of the module

        :return: a kickstart string
        """
        return self.implementation.generate_kickstart()

    def Quit(self):
        """Shut the module down."""
        self.implementation.stop()
