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
from pyanaconda.dbus.constants import DBUS_FLAG_NONE
from pyanaconda.core.signal import Signal

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["DBusObserverError", "DBusObjectObserver", "DBusCachedObserver"]


class DBusObserverError(Exception):
    """Exception class for the DBus observers."""
    pass


class DBusObserver(object):
    """Base class for DBus observers.

    This class is recommended to use only to watch the availability
    of a service on DBus. It doesn't provide any support for accessing
    objects provided by the service.

    Usage:

    # Create the observer and connect to its signals.
    observer = DBusObserver(SystemBus, "org.freedesktop.NetworkManager")

    def callback1(observer):
        print("Service is available!")

    def callback2(observer):
        print("Service is unavailable!")

    observer.service_available.connect(callback1)
    observer.service_unavailable.connect(callback2)

    # Connect to the service immediately.
    observer.connect()

    # Or connect to the service once it is available.
    # observer.connect_once_available()

    # Disconnect the observer.
    observer.disconnect()
    """

    def __init__(self, message_bus, service_name):
        """Creates an DBus service observer.

        :param message_bus: a message bus
        :param service_name: a DBus name of a service
        """
        self._message_bus = message_bus
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

    def connect(self):
        """Connect to the service immediately.

        :raise DBusObserverError: if service is not available
        """
        bus_proxy = self._message_bus.get_dbus_proxy()

        if not bus_proxy.NameHasOwner(self.service_name):
            raise DBusObserverError("Service {} is not available."
                                    .format(self._service_name))

        self._enable_service()
        self._watch()

    def connect_once_available(self):
        """Connect to the service once it is available.

        The observer is not connected to the service until it
        emits the service_available signal.
        """
        if self._message_bus.check_connection():
            self._watch()

    def disconnect(self):
        """Disconnect from the service.

        Disconnect from the service if it is connected and stop
        watching its availability.
        """
        if self._message_bus.check_connection():
            self._unwatch()

        if self.is_service_available:
            self._disable_service()

    def _watch(self):
        """Watch the service name on DBus."""
        bus = self._message_bus.connection
        num = bus.watch_name(self.service_name,
                             DBUS_FLAG_NONE,
                             self._service_name_appeared_callback,
                             self._service_name_vanished_callback)

        self._watched_id = num

    def _unwatch(self):
        """Stop to watch the service name on DBus."""
        bus = self._message_bus.connection
        bus.unwatch_name(self._watched_id)
        self._watched_id = None

    def _enable_service(self):
        """Enable the service."""
        self._is_service_available = True
        self._service_available.emit(self)

    def _disable_service(self):
        """Disable the service."""
        self._is_service_available = False
        self._service_unavailable.emit(self)

    def _service_name_appeared_callback(self, *args):
        """Callback for the watch method."""
        if not self.is_service_available:
            self._enable_service()

    def _service_name_vanished_callback(self, *args):
        """Callback for the watch method."""
        if self.is_service_available:
            self._disable_service()

    def __str__(self):
        """Returns a string version of this object."""
        return self._service_name

    def __repr__(self):
        """Returns a string representation."""
        return "{}({})".format(self.__class__.__name__,
                               self._service_name)


class DBusObjectObserver(DBusObserver):
    """Observer of a DBus object.

    This class is recommended to use when you are interested in only one
    object provided by a service. You can specify the object path in the
    __init__ method and access the proxy of the object in the proxy property.
    The proxy is cached.

    Usage:

    observer = DBusObjectObserver(SystemBus, "org.freedesktop.NetworkManager",
                                  "org/freedesktop/NetworkManager/Settings")
    observer.connect()
    result = observer.proxy.ListConnections()
    print(result)

    """

    def __init__(self, message_bus, service_name, object_path):
        """Creates an DBus object observer.

        :param message_bus: a message bus
        :param service_name: a DBus name of a service
        :param object_path: a DBus path of an object
        """
        super().__init__(message_bus, service_name)
        self._proxy = None
        self._object_path = object_path

    @property
    def proxy(self):
        """"Returns a proxy of the remote object."""
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

    def __str__(self):
        """Returns a string version of this object."""
        return self._object_path

    def __repr__(self):
        """Returns a string representation."""
        return "{}({},{})".format(self.__class__.__name__,
                                  self._service_name,
                                  self._object_path)


class PropertiesCache(object):
    """Cache for properties."""

    def __init__(self):
        self._properties = dict()

    @property
    def properties(self):
        """Return a dictionary of properties."""
        return self._properties

    def update(self, properties):
        """Update the cached properties."""
        self._properties.update(properties)

    def __getattr__(self, name):
        """Get the cached property.

        Called when an attribute lookup has not found
        the attribute in the usual places.
        """
        if name not in self._properties:
            raise AttributeError("Unknown property {}.".format(name))

        return self._properties[name]

    def __setattr__(self, name, value):
        """Set the attribute.

        Called when an attribute assignment is attempted.
        Allow to set the attributes of this class, but
        nothing else.
        """
        # Only self._properties are allowed to be set.
        if name in {"_properties"}:
            return super().__setattr__(name, value)

        raise AttributeError("It is not allowed to set {}.".format(name))


class DBusCachedObserver(DBusObjectObserver):
    """Observer of a DBus object with cached properties.

    This is an extension of DBusObjectObserver that allows to cache properties
    of the remote object. The observer is connected to the PropertiesChanged
    signal of the remote object and updates its cache every time the signal
    is emitted. Then it emits its own cached_properties_changed signal.

    Only properties of specified interfaces will be cached.

    Usage:
    observer = DBusCachedObserver(SystemBus, "org.freedesktop.NetworkManager",
                                  "org/freedesktop/NetworkManager/Settings",
                                  ["org.freedesktop.NetworkManager.Settings"])
    observer.connect()
    print(observer.cache.Hostname)
    """

    def __init__(self, message_bus, service_name, object_path, watched_interfaces=None):
        """Create an observer with cached properties.

        Only properties of specified interfaces will be watched and cached.

        :param message_bus: a message bus
        :param service_name: a DBus name of a service
        :param object_path:  a DBus path of an object
        :param watched_interfaces: a list of interface names
        """
        super().__init__(message_bus, service_name, object_path)
        self._cache = PropertiesCache()
        self._cached_properties_changed = Signal()
        self._watched_interfaces = set()

        if watched_interfaces:
            self._watched_interfaces.update(watched_interfaces)

    @property
    def cache(self):
        """Returns a cache with properties of the remote object."""
        return self._cache

    @property
    def cached_properties_changed(self):
        """Signal that emits when cached properties are changed.

        The signal emits this observer with updated cache, a set of
        properties names that are changed and a set of properties
        names that are invalid

        Example of a callback:

            def callback(observer, changed, invalid):
                pass

        """
        return self._cached_properties_changed

    def force_update(self):
        """Force the update of the cache."""
        for interface in self._watched_interfaces:
            self._cache.update(self.proxy.GetAll(interface))

    def _enable_service(self):
        """Enable the service."""
        self._proxy = None
        self._is_service_available = True

        # Synchronize properties with the remote object.
        self.proxy.PropertiesChanged.connect(self._properties_changed_callback)
        self.force_update()

        # Send cached_properties_changed signal.
        observer = self
        names_changed = set(self._cache.properties.keys())
        names_invalid = set()

        self.service_available.emit(self)

        if names_changed or names_invalid:
            self.cached_properties_changed.emit(observer, names_changed, names_invalid)

    def _properties_changed_callback(self, interface, changed, invalid):
        """Callback for the DBus signal PropertiesChanged."""
        if interface not in self._watched_interfaces:
            return

        # Update the cache
        self._cache.update(changed)

        # Send a signal.
        observer = self
        names_changed = set(changed.keys())
        names_invalid = set(invalid)

        if names_changed or names_invalid:
            self.cached_properties_changed.emit(observer, names_changed, names_invalid)
