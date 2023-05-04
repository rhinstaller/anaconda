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
from dasbus.namespace import get_namespace_from_name, get_dbus_path, get_dbus_name
from dasbus.client.observer import DBusObserver, DBusObserverError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.namespaces import ADDONS_NAMESPACE
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.boss.kickstart_manager.local_observer import KickstartHandlingObserver

log = get_module_logger(__name__)


class ModuleObserver(DBusObserver, KickstartHandlingObserver):
    """Observer of an Anaconda module."""

    def __init__(self, message_bus, service_name):
        """Creates a module observer.

        :param message_bus: a message bus
        :param service_name: a DBus name of a service
        """
        super().__init__(message_bus, service_name)
        self._proxy = None
        self._is_addon = service_name.startswith(get_dbus_name(*ADDONS_NAMESPACE))
        self._namespace = get_namespace_from_name(service_name)
        self._object_path = get_dbus_path(*self._namespace)

    @property
    def is_addon(self):
        """Is the observed module an addon?

        :return: True or False
        """
        return self._is_addon

    @property
    def proxy(self):
        """Returns a proxy of the remote object."""
        if not self._is_service_available:
            raise DBusObserverError("Service {} is not available."
                                    .format(self._service_name))

        if not self._proxy:
            self._proxy = self._message_bus.get_proxy(self._service_name,
                                                      self._object_path)

        return self._proxy

    def _enable_service(self):
        """Enable the service."""
        self._proxy = None
        super()._enable_service()

    def _disable_service(self):
        """Disable the service"""
        self._proxy = None
        super()._disable_service()

    def __repr__(self):
        """Returns a string representation."""
        return "{}({},{})".format(self.__class__.__name__,
                                  self._service_name,
                                  self._object_path)

    @property
    def kickstart_commands(self):
        return self.proxy.KickstartCommands

    @property
    def kickstart_sections(self):
        return self.proxy.KickstartSections

    @property
    def kickstart_addons(self):
        return self.proxy.KickstartAddons

    def generate_kickstart(self):
        return self.proxy.GenerateKickstart()

    def read_kickstart(self, ks_string):
        return KickstartReport.from_structure(
            self.proxy.ReadKickstart(ks_string)
        )
