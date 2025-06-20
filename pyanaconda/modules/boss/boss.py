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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.boss.boss_interface import BossInterface
from pyanaconda.modules.boss.install_manager import InstallManager
from pyanaconda.modules.boss.installation import (
    RunInstallationTask,
)
from pyanaconda.modules.boss.kickstart_manager import KickstartManager
from pyanaconda.modules.boss.module_manager import ModuleManager
from pyanaconda.modules.common.base import Service
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.containers import TaskContainer

log = get_module_logger(__name__)

__all__ = ["Boss"]


class Boss(Service):
    """The Boss service."""

    def __init__(self):
        super().__init__()
        self._module_manager = ModuleManager()
        self._kickstart_manager = KickstartManager()
        self._install_manager = InstallManager()

        self._module_manager.module_observers_changed.connect(
            self._kickstart_manager.on_module_observers_changed
        )

        self._module_manager.module_observers_changed.connect(
            self._install_manager.on_module_observers_changed
        )

    def publish(self):
        """Publish the boss."""
        TaskContainer.set_namespace(BOSS.namespace)
        DBus.publish_object(BOSS.object_path, BossInterface(self))
        DBus.register_service(BOSS.service_name)

    def get_modules(self):
        """Get service names of running modules.

        Get a list of all running DBus modules (including addons)
        that were discovered and started by the boss.

        :return: a list of service names
        """
        return self._module_manager.get_service_names()

    def start_modules_with_task(self):
        """Start the modules with the task."""
        return self._module_manager.start_modules_with_task()

    def stop(self):
        """Stop all modules and then stop the boss."""
        self._module_manager.stop_modules()
        super().stop()

    def read_kickstart_file(self, path):
        """Read the specified kickstart file.

        :param path: a path to a file
        :returns: a kickstart report
        """
        log.info("Reading a kickstart file at %s.", path)
        return self._kickstart_manager.read_kickstart_file(path)

    def generate_kickstart(self):
        """Return a kickstart representation of modules.

        :return: a kickstart string
        """
        log.info("Generating kickstart data...")
        return self._kickstart_manager.generate_kickstart()

    def collect_requirements(self):
        """Collect requirements of the modules.

        :return: a list of requirements
        """
        return self._install_manager.collect_requirements()

    def install_with_tasks(self):
        """Return installation tasks of this module.

        FIXME: This is a temporary workaround for the Web UI.

        :return: a list of DBus paths of the installation tasks
        """

        return [
            RunInstallationTask(
                install_manager=self._install_manager,
            )
        ]

    def collect_configure_runtime_tasks(self):
        """Collect tasks for configuration of the runtime environment.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of task proxies
        """
        return self._install_manager.collect_configure_runtime_tasks()

    def collect_configure_bootloader_tasks(self, kernel_versions):
        """Collect tasks for configuration of the bootloader.

        FIXME: This is a temporary workaround for add-ons.

        :param kernel_versions: a list of kernel versions
        :return: a list of task proxies
        """
        return self._install_manager.collect_configure_bootloader_tasks(kernel_versions)

    def collect_install_system_tasks(self):
        """Collect tasks for installation of the system.

        FIXME: This is a temporary workaround for add-ons.

        :return: a list of task proxies
        """
        return self._install_manager.collect_install_system_tasks()

    def set_locale(self, locale):
        """Set locale of boss and all modules.

        :param str locale: locale to set
        """
        log.info("Setting locale of all modules to %s.", locale)
        super().set_locale(locale)
        self._module_manager.set_modules_locale(locale)
