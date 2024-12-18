#
# module_manager.py: Anaconda DBUS module management
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.boss.module_manager.start_modules import StartModulesTask

log = get_module_logger(__name__)


class ModuleManager:
    """A class for managing kickstart modules."""

    def __init__(self):
        self._module_observers = []
        self.module_observers_changed = Signal()

    @property
    def module_observers(self):
        """Return the modules observers."""
        return self._module_observers

    def set_module_observers(self, observers):
        """Set the module observers."""
        self._module_observers = observers
        self.module_observers_changed.emit(self._module_observers)

    def start_modules_with_task(self):
        """Start modules with the task."""
        task = StartModulesTask(
            message_bus=DBus,
            activatable=conf.anaconda.activatable_modules,
            forbidden=conf.anaconda.forbidden_modules,
            optional=conf.anaconda.optional_modules,
        )
        task.succeeded_signal.connect(
            lambda: self.set_module_observers(task.get_result())
        )
        return task

    def get_service_names(self):
        """Get service names of running modules.

        :return: a list of service names
        """
        names = []

        for observer in self.module_observers:
            if not observer.is_service_available:
                continue

            names.append(observer.service_name)

        return names

    def set_modules_locale(self, locale):
        """Set locale of all modules.

        :param str locale: locale to set
        """
        log.info("Setting locale of all modules to %s.", locale)
        for observer in self.module_observers:
            if not observer.is_service_available:
                log.warning("%s is not available when setting locale", observer)
                continue
            observer.proxy.SetLocale(locale)

    def stop_modules(self):
        """Tell all running modules to quit."""
        log.debug("Stop modules.")
        for observer in self.module_observers:
            if not observer.is_service_available:
                continue

            # Call synchronously, because we need to wait for the
            # modules to quit before the boss can quit itself.
            observer.proxy.Quit()
            log.debug("%s has quit.", observer)
