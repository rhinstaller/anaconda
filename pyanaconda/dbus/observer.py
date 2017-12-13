#
# Observers of remote DBus objects.
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import DBUS_FLAG_NONE
from pyanaconda.isignal import Signal

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["DBusObserverError", "DBusServiceObserver", "DBusObjectObserver"]


class DBusObserverError(Exception):
    """Exception class for the DBus observers."""
    pass


class DBusObserver(object):
    """Base class for DBus observers.

    This class is recommended to use only to watch the availability
    of a service on DBus. It doesn't provide any support for accessing
    objects provided by the service.

    Usage:

    def callback1(observer):
        print("Service is available!")

    def callback2(observer):
        print("Service is unavailable!")

    observer = DBusObserver("org.freedesktop.NetworkManager")
    observer.service_available.connect(callback1)
    observer.service_unavailable.connect(callback2)
    observer.watch()
    """

    def __init__(self, service_name):
        """Creates an DBus service observer.

        :param service_name: a DBus name of a service
        """
        self._service_name = service_name
        self._is_service_available = False

        self._service_available = Signal()
        self._service_unavailable = Signal()

        self._watched_id = None

    @property
    def service_name(self):
        """Returns a DBus name."""
        return self._service_name

    @property
    def is_service_available(self):
        """The proxy can be accessed."""
        return self._is_service_available

    @property
    def service_available(self):
        """Signal that emits when the service is available.

        Signal emits this class as an argument. You have to
        call the watch method to activate the signals.
        """
        return self._service_available

    @property
    def service_unavailable(self):
        """Signal that emits when the service is unavailable.

        Signal emits this class as an argument. You have to
        call the watch method to activate the signals.
        """
        return self._service_unavailable

    def watch(self):
        """Watch the service name on DBus."""
        bus = DBus.get_connection()
        num = bus.watch_name(self.service_name,
                             DBUS_FLAG_NONE,
                             self._service_name_appeared_callback,
                             self._service_name_vanished_callback)

        self._watched_id = num

    def unwatch(self):
        """Stop to watch the service name on DBus."""
        bus = DBus.get_connection()
        bus.unwatch_name(self._watched_id)
        self._watched_id = None

    def _service_name_appeared_callback(self, *args):
        """Callback for the watch method."""
        self._is_service_available = True
        self._service_available.emit(self)

    def _service_name_vanished_callback(self, *args):
        """Callback for the watch method."""
        self._is_service_available = False
        self._service_unavailable.emit(self)

    def __str__(self):
        """Returns a string version of this object."""
        return self._service_name

    def __repr__(self):
        """Returns a string representation."""
        return "{}({})".format(self.__class__.__name__,
                               self._service_name)


class DBusServiceObserver(DBusObserver):
    """Observer of a DBus service.

    This class is recommended to use when you want to also access
    the objects provided by the service. The class keeps the proxies
    of the remote objects in a cache and deletes the cache when the
    service is unavailable. Therefore, you shouldn't keep the proxies
    somewhere else.

    Usage:

    observer = DBusServiceObserver("org.freedesktop.NetworkManager")
    observer.watch()

    proxy = observer.get_proxy("org/freedesktop/NetworkManager/Settings")
    result = proxy.ListConnections()
    print(result)

    """

    def __init__(self, service_name):
        """Creates the DBus service observer.

        :param service_name: a DBus name of a service
        """
        super().__init__(service_name)
        self._proxies = dict()

    def get_proxy(self, object_path):
        """"Returns a proxy of the remote object."""
        if not self._is_service_available:
            raise DBusObserverError("Service %s is not available.",
                                    self._service_name)

        if object_path in self._proxies:
            return self._proxies.get(object_path)

        proxy = DBus.get_proxy(self._service_name, object_path)
        self._proxies[object_path] = proxy
        return proxy

    def _service_name_appeared_callback(self, *args):
        """Callback for the watch method."""
        self._proxies = dict()
        super()._service_name_appeared_callback(*args)

    def _service_name_vanished_callback(self, *args):
        """Callback for the watch method."""
        self._proxies = dict()
        super()._service_name_vanished_callback(*args)


class DBusObjectObserver(DBusObserver):
    """Observer of a DBus object.

    This class is recommended to use when you are interested in only one
    object provided by a service. You can specify the object path in the
    __init__ method and access the proxy of the object in the proxy property.
    The proxy is cached.

    Usage:

    observer = DBusObjectObserver("org.freedesktop.NetworkManager",
                                  "org/freedesktop/NetworkManager/Settings")
    observer.watch()
    result = observer.proxy.ListConnections()
    print(result)

    """

    def __init__(self, service_name, object_path):
        """Creates an DBus object observer.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path of an object
        """
        super().__init__(service_name)
        self._proxy = None
        self._object_path = object_path

    @property
    def proxy(self):
        """"Returns a proxy of the remote object."""
        if not self._is_service_available:
            raise DBusObserverError("Service %s is not available.",
                                    self._service_name)

        if not self._proxy:
            self._proxy = DBus.get_proxy(self._service_name,
                                         self._object_path)

        return self._proxy

    def _service_name_appeared_callback(self, *args):
        """Callback for the watch method."""
        self._proxy = None
        super()._service_name_appeared_callback(*args)

    def _service_name_vanished_callback(self, *args):
        """Callback for the watch method."""
        self._proxy = None
        super()._service_name_vanished_callback(*args)

    def __str__(self):
        """Returns a string version of this object."""
        return self._object_path

    def __repr__(self):
        """Returns a string representation."""
        return "{}({},{})".format(self.__class__.__name__,
                                  self._service_name,
                                  self._object_path)
