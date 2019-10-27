#
# Templates for DBus interfaces
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
from abc import ABC

from dasbus.server.property import PropertiesInterface

__all__ = ["BasicInterfaceTemplate", "InterfaceTemplate"]


class BasicInterfaceTemplate(ABC):
    """Basic template for a DBus interface.

    This template uses a software design pattern called proxy.

    This class provides a recommended way how to define DBus interfaces
    and create publishable DBus objects. The class that defines a DBus
    interface should inherit this class and be decorated with @dbus_class
    or @dbus_interface decorator. The implementation of this interface will
    be provided by a separate object called implementation. Therefore the
    methods of this class should call the methods of the implementation,
    the signals should be connected to the signals of the implementation
    and the getters and setters of properties should access the properties
    of the implementation.

    Example:

    @dbus_interface("org.myproject.X")
    class InterfaceX(BasicInterfaceTemplate):
        def DoSomething(self) -> Str:
            return self.implementation.do_something()

    class X(object):
        def do_something(self):
            return "Done!"

    x = X()
    i = InterfaceX(x)

    DBus.publish_object("/org/myproject/X", i)
    """

    def __init__(self, implementation):
        """Create a publishable DBus object.

        :param implementation: an implementation of this interface
        """
        self._implementation = implementation
        self.connect_signals()

    @property
    def implementation(self):
        """Return the implementation of this interface.

        :return: an implementation
        """
        return self._implementation

    def connect_signals(self):
        """Interconnect the signals.

        You should connect the emit methods of the interface
        signals to the signals of the implementation. Every
        time the implementation emits a signal, this interface
        reemits the signal on DBus.
        """
        pass


class InterfaceTemplate(BasicInterfaceTemplate, PropertiesInterface):
    """Template for a DBus interface.

    The interface provides the support for the standard interface
    org.freedesktop.DBus.Properties.

    Usage:

        def connect_signals(self):
            super().connect_signals()

            self.implementation.module_properties_changed.connect(self.flush_changes)
            self.watch_property("X", self.implementation.x_changed)

        @property
        def X(self, x) -> Int:
            return self.implementation.x

        @emits_properties_changed
        def SetX(self, x: Int):
            self.implementation.set_x(x)

    """

    def __init__(self, implementation):
        PropertiesInterface.__init__(self)
        BasicInterfaceTemplate.__init__(self, implementation)

    def watch_property(self, property_name, signal):
        """Watch a DBus property.

        Report a change when the property is changed.

        :param property_name: a name of a DBus property
        :param signal: a signal that emits when the property is changed
        """
        self._properties_changes.check_property(property_name)
        signal.connect(lambda *args, **kwargs: self.report_changed_property(property_name))
