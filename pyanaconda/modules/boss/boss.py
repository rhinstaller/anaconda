# boss.py
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

from pyanaconda.core.async_utils import run_in_loop
from pyanaconda.dbus import DBus
from pyanaconda.dbus.objects import BOSS, BOSS_INSTALLATION
from pyanaconda.modules.boss.boss_interface import AnacondaBossInterface
from pyanaconda.modules.base import BaseModule
from pyanaconda.modules.boss.module_manager import ModuleManager
from pyanaconda.modules.boss.install_manager.installation_interface import InstallationInterface
from pyanaconda.modules.boss.install_manager.install_manager import InstallManager
from pyanaconda.modules.boss.kickstart_manager import KickstartManager

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


class Boss(BaseModule):
    """The Boss module."""

    def __init__(self, module_manager=None, install_manager=None, kickstart_manager=None):
        super().__init__()
        self._module_manager = module_manager or ModuleManager()
        self._install_manager = install_manager or InstallManager()
        self._kickstart_manager = kickstart_manager or KickstartManager()

        self._setup_install_manager()
        self._setup_kickstart_manager()

    def _setup_install_manager(self):
        """Set up the install manager."""
        # FIXME: the modules list must to be readable from inside of InstallManager when needed
        # the modules needs to be passed to the InstallManager some other way
        # basically we need to be able to load modules from everywhere when we need them
        modules = self._module_manager.module_observers
        self._install_manager.module_observers = modules

    def _setup_kickstart_manager(self):
        """Set up the kickstart manager."""
        modules = self._module_manager.module_observers
        self._kickstart_manager.module_observers = modules

    def publish(self):
        """Publish the boss."""
        DBus.publish_object(BOSS.object_path,
                            AnacondaBossInterface(self))
        DBus.publish_object(BOSS_INSTALLATION.object_path,
                            InstallationInterface(self._install_manager))
        DBus.register_service(BOSS.service_name)

    def run(self):
        """Run the boss's loop."""
        log.debug("Gather the modules.")
        self._module_manager.add_default_modules()
        self._module_manager.add_addon_modules()
        log.debug("Schedule publishing.")
        run_in_loop(self.publish)
        log.debug("Schedule startup of modules.")
        run_in_loop(self._module_manager.start_modules)
        log.info("starting mainloop")
        self._loop.run()

    def stop(self):
        """Stop all modules and then stop the boss."""
        self._module_manager.stop_modules()
        super().stop()

    @property
    def all_modules_available(self):
        """Are all modules available?

        FIXME: This is a temporary method, because it provides
        an implementation to the AnacondaBossInterface.
        """
        return self._module_manager.check_modules_availability()

    @property
    def unprocessed_kickstart(self):
        """Return an unprocessed part of a kickstart.

        FIXME: This is a temporary method, because it provides
        an implementation to the AnacondaBossInterface.
        """
        return self._kickstart_manager.unprocessed_kickstart

    def split_kickstart(self, path):
        """Split a kickstart file.

        FIXME: This is a temporary method, because it provides
        an implementation to the AnacondaBossInterface.
        """
        log.info("Splitting kickstart from %s.", path)
        self._kickstart_manager.split(path)

    def distribute_kickstart(self):
        """Distribute a kickstart file.

        FIXME: This is a temporary method, because it provides
        an implementation to the AnacondaBossInterface.
        """
        log.info("Distributing kickstart.")
        return self._kickstart_manager.distribute()
