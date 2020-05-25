#
# Support for object containers
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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
from queue import Queue

from pyanaconda.anaconda_loggers import get_module_logger
from dasbus.constants import DBUS_FLAG_NONE, DBUS_START_REPLY_SUCCESS
from dasbus.namespace import get_dbus_name
from pyanaconda.modules.boss.module_manager import ModuleObserver
from pyanaconda.modules.common.constants.namespaces import ADDONS_NAMESPACE
from pyanaconda.modules.common.errors.module import UnavailableModuleError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["StartModulesTask"]


class StartModulesTask(Task):
    """A task for starting DBus modules.

    The timeout service_start_timeout from the Anaconda bus
    configuration file is applied by default when the DBus
    method StartServiceByName is called.
    """

    def __init__(self, message_bus, module_names, addons_enabled):
        """Create a new task.

        :param message_bus: a message bus
        :param module_names: a list of DBus names of modules
        :param addons_enabled: True to enable addons, otherwise False
        """
        super().__init__()
        self._message_bus = message_bus
        self._module_names = module_names
        self._addons_enabled = addons_enabled
        self._module_observers = []
        self._callbacks = Queue()

    @property
    def name(self):
        """Name of the task."""
        return "Start the modules"

    def run(self):
        """Run the task.

        :return: a list of observers
        """
        # Collect the modules.
        self._module_observers = self._find_modules() + self._find_addons()

        # All modules are unavailable now.
        unavailable = set(self._module_observers)

        # Asynchronously start the modules.
        self._start_modules(self._module_observers)

        # Process callbacks of the asynchronous calls until all modules
        # are available. A callback returns an observer of an available
        # module or None. If a DBus call fails with an error, we raise
        # an exception in the callback and immediately quit the task.
        while unavailable:
            callback = self._callbacks.get()
            unavailable.discard(callback())

        return self._module_observers

    def _find_modules(self):
        """Find modules."""
        modules = []

        for service_name in self._module_names:
            log.debug("Found %s.", service_name)
            modules.append(ModuleObserver(
                self._message_bus,
                service_name
            ))

        return modules

    def _find_addons(self):
        """Find additional modules."""
        modules = []

        if not self._addons_enabled:
            return modules

        dbus = self._message_bus.proxy
        names = dbus.ListActivatableNames()
        prefix = get_dbus_name(*ADDONS_NAMESPACE)

        for service_name in names:
            if not service_name.startswith(prefix):
                continue

            log.debug("Found %s.", service_name)
            modules.append(ModuleObserver(
                self._message_bus,
                service_name,
                is_addon=True
            ))

        return modules

    def _start_modules(self, module_observers):
        """Start the modules."""
        dbus = self._message_bus.proxy

        for observer in module_observers:
            log.debug("Starting %s", observer)

            dbus.StartServiceByName(
                observer.service_name,
                DBUS_FLAG_NONE,
                callback=self._start_service_by_name_callback,
                callback_args=(observer,)
            )

    def _start_service_by_name_callback(self, *args, **kwargs):
        """Callback for the StartServiceByName method."""
        self._callbacks.put(lambda: self._start_service_by_name_handler(*args, **kwargs))

    def _start_service_by_name_handler(self, call, observer):
        """Handler for the StartServiceByName method."""
        try:
            returned = call()
        except Exception as error:  # pylint: disable=broad-except
            raise UnavailableModuleError(
                "Service {} has failed to start: {}".format(observer, error)
            ) from error

        if returned != DBUS_START_REPLY_SUCCESS:
            log.warning("Service %s is already running.", observer)
        else:
            log.debug("Service %s started successfully.", observer)

        # Connect the observer once the service is available.
        observer.service_available.connect(self._service_available_callback)
        observer.connect_once_available()

    def _service_available_callback(self, *args, **kwargs):
        """Callback for the service_available signal."""
        self._callbacks.put(lambda: self._service_available_handler(*args, **kwargs))

    def _service_available_handler(self, observer):
        """Handler for the service_available signal."""
        log.debug("%s is available.", observer)
        observer.proxy.Ping()
        return observer
