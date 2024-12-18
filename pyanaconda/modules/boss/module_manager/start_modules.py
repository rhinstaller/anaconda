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
from functools import partial
from queue import SimpleQueue

from dasbus.constants import DBUS_FLAG_NONE, DBUS_START_REPLY_SUCCESS

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.boss.module_manager.module_observer import ModuleObserver
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

    def __init__(self, message_bus, activatable, forbidden, optional):
        """Create a new task.

        Anaconda modules are specified by their full DBus name or a prefix
        of their DBus name that ends with '*'.

        :param message_bus: a message bus
        :param activatable: a list of modules that can be activated.
        :param forbidden: a list of modules that are are not allowed to run
        :param optional: a list of modules that are optional
        """
        super().__init__()
        self._message_bus = message_bus
        self._activatable = activatable
        self._forbidden = forbidden
        self._optional = optional
        self._module_observers = []
        self._callbacks = SimpleQueue()

    @property
    def name(self):
        """Name of the task."""
        return "Start the modules"

    def run(self):
        """Run the task.

        :return: a list of observers
        """
        # Collect the modules.
        self._module_observers = self._find_modules()

        # Asynchronously start the modules.
        self._start_modules(self._module_observers)

        # Process the callbacks of the asynchronous calls.
        self._process_callbacks(self._module_observers)

        return self._module_observers

    @staticmethod
    def _match_module(name, patterns):
        """Match a module with one of the specified patterns."""
        for pattern in patterns:
            # Match the name prefix.
            if pattern.endswith("*") and name.startswith(pattern[:-1]):
                return True

            # Match the full name.
            if name == pattern:
                return True

        return False

    def _find_modules(self):
        """Find modules to start."""
        modules = []

        dbus = self._message_bus.proxy
        names = dbus.ListActivatableNames()

        for service_name in names:
            # Only activatable modules can be started.
            if not self._match_module(service_name, self._activatable):
                continue

            # Forbidden modules are not allowed to run.
            if self._match_module(service_name, self._forbidden):
                log.debug(
                    "Skip %s. The module won't be started, because it's "
                    "marked as forbidden in the Anaconda configuration "
                    "files.", service_name
                )
                continue

            log.debug("Found %s.", service_name)
            modules.append(ModuleObserver(
                self._message_bus,
                service_name,
            ))

        return modules

    def _start_modules(self, module_observers):
        """Start the modules."""
        dbus = self._message_bus.proxy

        for observer in module_observers:
            log.debug("Starting %s.", observer)

            dbus.StartServiceByName(
                observer.service_name,
                DBUS_FLAG_NONE,
                callback=self._start_service_by_name_callback,
                callback_args=(observer,)
            )

    def _start_service_by_name_callback(self, call, observer):
        """Callback for the StartServiceByName method."""
        self._callbacks.put((observer, partial(self._start_service_by_name_handler, call)))

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
        return False

    def _service_available_callback(self, observer):
        """Callback for the service_available signal."""
        self._callbacks.put((observer, self._service_available_handler))

    def _service_available_handler(self, observer):
        """Handler for the service_available signal."""
        log.debug("%s is available.", observer)
        observer.proxy.Ping()
        return True

    def _process_callbacks(self, module_observers):
        """Process callbacks of the asynchronous calls.

        Process callbacks of the asynchronous calls until all modules
        are processed. A callback returns True if the module is processed,
        otherwise False.

        If a DBus call fails with an error, we raise an exception in the
        callback and immediately quit the task unless it comes from an
        add-on. A failure of an add-on module is not fatal, we just remove
        its observer from the list of available modules and continue.

        :param module_observers: a list of module observers
        """
        available = module_observers
        unprocessed = set(module_observers)

        while unprocessed:
            # Call the next scheduled callback.
            observer, callback = self._callbacks.get()

            try:
                is_available = callback(observer)

                # The module is not processed yet.
                if not is_available:
                    continue

            except UnavailableModuleError:
                # The failure of a required module is fatal.
                if not self._match_module(observer.service_name, self._optional):
                    raise

                # The failure of an optional module is not fatal. Remove
                # it from the list of available modules and continue.
                log.debug(
                    "Skip %s. The optional module has failed to start, "
                    "so it won't be available during the installation.",
                    observer.service_name
                )
                available.remove(observer)

            # The module is processed.
            unprocessed.discard(observer)
