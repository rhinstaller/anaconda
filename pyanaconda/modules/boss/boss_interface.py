# boss_interface.py
# Anaconda main DBUS module & module manager.
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
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.objects import BOSS, BOSS_ANACONDA
from pyanaconda.dbus.template import InterfaceTemplate
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.typing import Bool, Str, Int


@dbus_interface(BOSS.interface_name)
class BossInterface(InterfaceTemplate):
    """DBus interface for the Boss."""

    def Quit(self):
        """Stop all modules and then stop the boss."""
        self.implementation.stop()


@dbus_interface(BOSS_ANACONDA.interface_name)
class AnacondaBossInterface(BossInterface):
    """Temporary extension of the boss for anaconda.

    Used for synchronization with anaconda during transition.
    """

    @property
    def AllModulesAvailable(self) -> Bool:
        """Returns true if all modules are available."""
        return self.implementation.all_modules_available

    @property
    def UnprocessedKickstart(self) -> Str:
        """Returns kickstart containing parts that are not handled by any module."""
        return self.implementation.unprocessed_kickstart

    def SplitKickstart(self, path: Str):
        """Splits the kickstart for modules.

        :raises SplitKickstartError: if parsing fails
        """
        self.implementation.split_kickstart(path)

    def DistributeKickstart(self) -> List[Dict[Str, Variant]]:
        """Distributes kickstart to modules synchronously.

        Assumes all modules are started.

        :returns: list of kickstart errors
        """
        results = self.implementation.distribute_kickstart()

        return [{
            "module_name": get_variant(Str, result["module_name"]),
            "file_name": get_variant(Str, result["file_name"]),
            "line_number": get_variant(Int, result["line_number"]),
            "error_message": get_variant(Str, result["error_message"])
        } for result in results]
