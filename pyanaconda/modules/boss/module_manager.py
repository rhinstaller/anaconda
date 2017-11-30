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
from pyanaconda.dbus.constants import ANACONDA_SERVICES, DBUS_START_REPLY_SUCCESS, \
    DBUS_ADDON_NAMESPACE

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class ModuleManager(object):

    def __init__(self):
        self._started_module_services = []
        self._failed_module_services = []
        self._addon_module_services = []

    @property
    def addon_module_services(self):
        return self._addon_module_services

    @property
    def expected_module_services(self):
        expected_modules = []
        expected_modules.extend(ANACONDA_SERVICES)
        expected_modules.extend(self.addon_module_services)
        return expected_modules

    @property
    def running_module_services(self):
        # For our purpose, just this
        return self._started_module_services

    @property
    def modules_starting_finished(self):
        return set(self._started_module_services + self._failed_module_services) == set(self.expected_module_services)

    def _finish_start_service_cb(self, service, returned=None, error=None):
        """Callback for dbus.StartServiceByName."""
        if error:
            log.debug("%s error: %s", service, error)
            self._failed_module_services.append(service)
        elif returned:
            if returned == DBUS_START_REPLY_SUCCESS:
                log.debug("%s started successfully, returned: %s)", service, returned)
                self._started_module_services.append(service)
            else:
                log.warning("%s is already running, returned: %s", service, returned)
        else:
            log.error("%s failed to start without even returning anything", service)

        self.check_modules_started()

    def check_modules_started(self):
        if self.modules_starting_finished:
            log.debug("modules starting finished, running: %s failed: %s",
                      self._started_module_services,
                      self._failed_module_services)
            for service in self._started_module_services:
                # FIXME: This is just a temporary solution.
                module = DBus.get_proxy(service, auto_object_path(service))
                module.EchoString("Boss told me - some modules were started: %s and some might have failed: %s." %
                                  (self._started_module_services, self._failed_module_services))
            return True
        else:
            return False

    def find_addons(self):
        self._addon_module_services = []
        dbus = DBus.get_dbus_proxy()
        names = dbus.ListActivatableNames()
        for name in names:
            if name.startswith(DBUS_ADDON_NAMESPACE):
                self._addon_module_services.append(name)


    def check_no_modules_are_running(self):
        dbus = DBus.get_dbus_proxy()
        for service in self.expected_module_services:
            if dbus.NameHasOwner(service):
                log.error("service %s has unexpected owner", service)

    def start_modules(self):
        """Starts anaconda modules (including addons)."""
        log.debug("starting modules")
        self.check_no_modules_are_running()

        dbus = DBus.get_dbus_proxy()
        for service in self.expected_module_services:
            log.debug("Starting %s", service)
            try:
                dbus.StartServiceByName(service, 0, callback=self._finish_start_service_cb, callback_args=(service,))
            except Exception:  # pylint: disable=broad-except
                self._failed_module_services.append(service)
                log.exception("module startup failed")

        log.debug("started all modules")

    def stop_modules(self):
        """Tells all running modules to quit."""
        log.debug("sending Quit to all modules and addons")
        for service in self.running_module_services:
            # FIXME: This is just a temporary solution.
            module = DBus.get_proxy(service, auto_object_path(service))
            # TODO: async ?
            # possible reasons:
            # - module hanging in Quit, deadlocking shutdown
            try:
                module.Quit()
            except Exception:  # pylint: disable=broad-except
                log.exception("Quit failed for module: %s", service)
