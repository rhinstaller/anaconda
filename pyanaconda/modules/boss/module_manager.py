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
from pydbus.auto_names import auto_object_path

from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import ANACONDA_MODULES, DBUS_START_REPLY_SUCCESS, \
    DBUS_ADDON_NAMESPACE, DBUS_FLAG_NONE
from pyanaconda.dbus.observer import DBusObjectObserver

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class ModuleManager(object):
    """A class for managing kickstart modules."""

    def __init__(self):
        self._module_observers = []

    @property
    def module_observers(self):
        """Return the modules observers."""
        return self._module_observers

    def add_module(self, service_name, module_path):
        """Add module to manage."""
        observer = DBusObjectObserver(service_name, module_path)
        self._module_observers.append(observer)

    def add_default_modules(self):
        """Add the default modules."""
        for name, path in ANACONDA_MODULES:
            self.add_module(name, path)

    def add_addon_modules(self):
        """Add the addon modules."""
        dbus = DBus.get_dbus_proxy()
        names = dbus.ListActivatableNames()

        for name in names:
            if name.startswith(DBUS_ADDON_NAMESPACE):
                self.add_module(name, auto_object_path(name))

    def start_modules(self):
        """Start anaconda modules (including addons)."""
        log.debug("Start modules.")
        dbus = DBus.get_dbus_proxy()

        for observer in self.module_observers:
            log.debug("Starting %s", observer)
            dbus.StartServiceByName(observer.service_name,
                                    DBUS_FLAG_NONE,
                                    callback=self._start_modules_callback,
                                    callback_args=(observer,))

            # Watch the module.
            observer.service_available.connect(self._process_module_is_available)
            observer.service_unavailable.connect(self._process_module_is_unavailable)
            observer.watch()

    def _start_modules_callback(self, service, returned, error):
        """Callback for start_modules."""
        if error:
            log.error("Service %s failed to start: %s", service, error)
            return

        if returned != DBUS_START_REPLY_SUCCESS:
            log.warning("Service %s is already running.", service)
        else:
            log.debug("Service %s started successfully.", service)

        if self.check_modules_availability():
            log.info("All modules are ready now.")

    def _process_module_is_available(self, observer):
        """Process the service_available signal."""
        log.debug("%s is available", observer)
        observer.proxy.Ping("Boss says hi!")

    def _process_module_is_unavailable(self, observer):
        """Process the service_unavailable signal."""
        log.debug("%s is unavailable", observer)

    def check_modules_availability(self):
        """Check if all modules are available.

        :returns: True if all modules are available, otherwise False
        """
        for observer in self.module_observers:
            if not observer.is_service_available:
                return False

        return True

    def stop_modules(self):
        """Tell all running modules to quit."""
        log.debug("Stop modules.")
        for observer in self.module_observers:
            if not observer.is_service_available:
                continue

            # Call asynchronously to avoid problems.
            observer.proxy.Quit(callback=self._stop_modules_callback,
                                callback_args=(observer,))

    def _stop_modules_callback(self, observer, returned, error):
        """Callback for stop_modules."""
        log.debug("%s has quit.", observer)
