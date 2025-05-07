#
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.client.proxy import get_object_handler
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base.base_template import InterfaceTemplate
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.custom_typing import BusName
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.common.structures.requirement import Requirement

__all__ = ["BossInterface"]


def get_proxy_identification(proxy):
    """Get a service name and an object path of the given DBus proxy.

    :param proxy: a proxy of a remote DBus object
    :return: a service name and an object path of the DBus object
    """
    handler = get_object_handler(proxy)
    return handler.service_name, handler.object_path


@dbus_interface(BOSS.interface_name)
class BossInterface(InterfaceTemplate):
    """DBus interface for the Boss."""

    def GetModules(self) -> List[BusName]:
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

    def CollectRequirements(self) -> List[Structure]:
        """Collect requirements of the modules.

        :return: a list of DBus structures of the type Requirement
        """
        return Requirement.to_structure_list(
            self.implementation.collect_requirements()
        )

    def InstallWithTasks(self) -> List[ObjPath]:
        """Returns installation tasks of this module.

        :returns: list of object paths of installation tasks
        """
        return TaskContainer.to_object_path_list(
            self.implementation.install_with_tasks()
        )

    def CollectConfigureRuntimeTasks(self) -> List[Tuple[BusName, ObjPath]]:
        """Collect tasks for configuration of the runtime environment.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of service names and object paths of tasks
        """
        proxies = self.implementation.collect_configure_runtime_tasks()
        return list(map(get_proxy_identification, proxies))

    def CollectConfigureBootloaderTasks(self, kernel_versions: List[Str]) \
            -> List[Tuple[BusName, ObjPath]]:
        """Collect tasks for configuration of the bootloader.

        FIXME: This is a temporary workaround for add-ons.

        :param kernel_versions: a list of kernel versions
        :return: a list of service names and object paths of tasks
        """
        proxies = self.implementation.collect_configure_bootloader_tasks(kernel_versions)
        return list(map(get_proxy_identification, proxies))

    def CollectInstallSystemTasks(self) -> List[Tuple[BusName, ObjPath]]:
        """Collect tasks for installation of the system.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of service names and object paths of tasks
        """
        proxies = self.implementation.collect_install_system_tasks()
        return list(map(get_proxy_identification, proxies))

    def Quit(self):
        """Stop all modules and then stop the boss."""
        self.implementation.stop()
