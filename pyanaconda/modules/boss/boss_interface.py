# boss_interface.py
# Anaconda main DBus module & module manager.
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
from dasbus.server.interface import dbus_interface
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.base.base_template import InterfaceTemplate
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.kickstart import KickstartReport


@dbus_interface(BOSS.interface_name)
class BossInterface(InterfaceTemplate):
    """DBus interface for the Boss."""

    def GetModules(self) -> List[Str]:
        """Get service names of running modules.

        Get a list of all running DBus modules (including addons)
        that were discovered and started by the boss.

        :return: a list of service names
        """
        return self.implementation.get_modules()

    def StartModulesWithTask(self) -> ObjPath:
        """Start modules with the task.

        :return: a DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.start_modules_with_task()
        )

    def ReadKickstartFile(self, path: Str) -> Structure:
        """Read the specified kickstart file.

        :param path: a path to a file
        :returns: a structure with a kickstart report
        """
        return KickstartReport.to_structure(
            self.implementation.read_kickstart_file(path)
        )

    def GenerateKickstart(self) -> Str:
        """Return a kickstart representation of modules.

        :return: a kickstart string
        """
        return self.implementation.generate_kickstart()

    def SetLocale(self, locale: Str):
        """Set locale of boss and all modules.

        Examples: "cs_CZ.UTF-8", "fr_FR"
        """
        self.implementation.set_locale(locale)

    def ConfigureRuntimeWithTask(self) -> ObjPath:
        """Configure the runtime environment.

        FIXME: This method temporarily uses only addons.

        :return: a DBus path a task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_runtime_with_task()
        )

    def InstallSystemWithTask(self) -> ObjPath:
        """Install the system.

        FIXME: This method temporarily uses only addons.

        :return: a DBus path of a task
        """
        return TaskContainer.to_object_path(
            self.implementation.install_system_with_task()
        )

    def Quit(self):
        """Stop all modules and then stop the boss."""
        self.implementation.stop()
