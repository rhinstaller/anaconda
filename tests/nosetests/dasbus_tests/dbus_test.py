#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from threading import Thread, Event
from unittest import mock
from unittest.mock import Mock

from dasbus.client.proxy import disconnect_proxy
from dasbus.connection import AddressedMessageBus
from dasbus.error import map_error
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.typing import *  # pylint: disable=wildcard-import

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib


class run_in_glib(object):
    """Run the test methods in GLib.

    :param timeout: Timeout in seconds when the loop will be killed.
    """

    def __init__(self, timeout):
        self._timeout = timeout
        self._result = None

    def __call__(self, func):

        def kill_loop(loop):
            loop.quit()
            return False

        def run_in_loop(*args, **kwargs):
            self._result = func(*args, **kwargs)

        def create_loop(*args, **kwargs):
            loop = GLib.MainLoop()

            GLib.idle_add(run_in_loop, *args, **kwargs)
            GLib.timeout_add_seconds(self._timeout, kill_loop, loop)

            loop.run()

            return self._result

        return create_loop


@map_error("my.testing.Error")
class ExampleException(Exception):
    pass


@dbus_interface("my.testing.Example")
class ExampleInterface(object):

    def __init__(self):
        self._knocked = False
        self._names = []
        self._values = [0]
        self._secrets = []

    @property
    def Name(self) -> Str:
        return "My example"

    @property
    def Value(self) -> Int:
        return self._values[-1]

    @Value.setter
    def Value(self, value: Int):
        self._values.append(value)
        self.PropertiesChanged(
            "my.testing.Example",
            {"Value": get_variant(Int, value)},
            ["Name"]
        )

    def _set_secret(self, secret: Str):
        self._secrets.append(secret)

    Secret = property(fset=_set_secret)

    def Knock(self):
        self._knocked = True
        self.Knocked()

    def Hello(self, name: Str) -> Str:
        self._names.append(name)
        self.Visited(name)
        return "Hello, {}!".format(name)

    @dbus_signal
    def Knocked(self):
        pass

    @dbus_signal
    def Visited(self, name: Str):
        pass

    def Raise(self, message: Str):
        raise ExampleException(message)

    @dbus_signal
    def PropertiesChanged(self, interface: Str, changed: Dict[Str, Variant], invalid: List[Str]):
        pass


class DBusTestCase(unittest.TestCase):
    """Test DBus support with a real DBus connection."""

    TIMEOUT = 3

    def setUp(self):
        self.bus = Gio.TestDBus()
        self.bus.up()
        self.message_bus = AddressedMessageBus(self.bus.get_bus_address())

        self.service = None
        self.clients = []

    def tearDown(self):
        self.message_bus.disconnect()
        self.bus.down()

    def message_bus_test(self):
        """Test the message bus."""
        self.assertTrue(self.message_bus.check_connection())
        self.assertEqual(self.message_bus.address, self.bus.get_bus_address())
        self.assertEqual(self.message_bus.proxy.Ping(), None)

    def _set_service(self, service):
        self.service = service

    def _add_client(self, client_test):
        thread = Thread(None, client_test)
        thread.daemon = True
        self.clients.append(thread)

    def _get_proxy(self):
        return self.message_bus.get_proxy(
            "my.testing.Example",
            "/my/testing/Example"
        )

    def _run_test(self):
        self.message_bus.publish_object(
            "/my/testing/Example",
            self.service
        )

        self.message_bus.register_service(
            "my.testing.Example"
        )

        for client in self.clients:
            client.start()

        self.assertTrue(self._run_service())

        for client in self.clients:
            client.join()

    @run_in_glib(TIMEOUT)
    def _run_service(self):
        return True

    def knock_test(self):
        """Call a simple DBus method."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._knocked, False)

        def test():
            proxy = self._get_proxy()
            self.assertEqual(None, proxy.Knock())

        self._add_client(test)
        self._run_test()

        self.assertEqual(self.service._knocked, True)

    def hello_test(self):
        """Call a DBus method."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._names, [])

        def test1():
            proxy = self._get_proxy()
            self.assertEqual("Hello, Foo!", proxy.Hello("Foo"))

        def test2():
            proxy = self._get_proxy()
            self.assertEqual("Hello, Bar!", proxy.Hello("Bar"))

        self._add_client(test1)
        self._add_client(test2)
        self._run_test()

        self.assertEqual(sorted(self.service._names), ["Bar", "Foo"])

    def name_test(self):
        """Use a DBus read-only property."""
        self._set_service(ExampleInterface())

        def test1():
            proxy = self._get_proxy()
            self.assertEqual("My example", proxy.Name)

        def test2():
            proxy = self._get_proxy()
            self.assertEqual("My example", proxy.Name)

        def test3():
            proxy = self._get_proxy()
            with self.assertRaises(AttributeError):
                proxy.Name = "Another example"

            self.assertEqual("My example", proxy.Name)

        self._add_client(test1)
        self._add_client(test2)
        self._add_client(test3)
        self._run_test()

    def secret_test(self):
        """Use a DBus write-only property."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._secrets, [])

        def test1():
            proxy = self._get_proxy()
            proxy.Secret = "Secret 1"

        def test2():
            proxy = self._get_proxy()
            proxy.Secret = "Secret 2"

        def test3():
            proxy = self._get_proxy()
            with self.assertRaises(AttributeError):
                self.fail(proxy.Secret)

        self._add_client(test1)
        self._add_client(test2)
        self._add_client(test3)
        self._run_test()

        self.assertEqual(sorted(self.service._secrets), ["Secret 1", "Secret 2"])

    def value_test(self):
        """Use a DBus read-write property."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._values, [0])

        def test1():
            proxy = self._get_proxy()
            self.assertIn(proxy.Value, (0, 3, 4))
            proxy.Value = 1
            self.assertIn(proxy.Value, (1, 3, 4))
            proxy.Value = 2
            self.assertIn(proxy.Value, (2, 3, 4))

        def test2():
            proxy = self._get_proxy()
            self.assertIn(proxy.Value, (0, 1, 2))
            proxy.Value = 3
            self.assertIn(proxy.Value, (3, 1, 2))
            proxy.Value = 4
            self.assertIn(proxy.Value, (4, 1, 2))

        self._add_client(test1)
        self._add_client(test2)
        self._run_test()

        self.assertEqual(sorted(self.service._values), [0, 1, 2, 3, 4])
        self.assertEqual(self.service._values[0], 0)
        self.assertLess(self.service._values.index(1), self.service._values.index(2))
        self.assertLess(self.service._values.index(3), self.service._values.index(4))

    def knocked_test(self):
        """Use a simple DBus signal."""
        self._set_service(ExampleInterface())
        event = Event()
        knocked = Mock()

        def callback():
            knocked("Knocked!")

        def test_1():
            proxy = self._get_proxy()
            proxy.Knocked.connect(callback)
            event.set()

        def test_2():
            event.wait()
            proxy = self._get_proxy()
            proxy.Knock()
            proxy.Knock()
            proxy.Knock()

        self._add_client(test_1)
        self._add_client(test_2)
        self._run_test()

        knocked.assert_has_calls([
            mock.call("Knocked!"),
            mock.call("Knocked!"),
            mock.call("Knocked!")
        ])

    def visited_test(self):
        """Use a DBus signal."""
        self._set_service(ExampleInterface())
        event = Event()
        visited = Mock()

        def callback(name):
            visited("Visited by {}.".format(name))

        def test1():
            proxy = self._get_proxy()
            proxy.Visited.connect(callback)
            event.set()

        def test2():
            event.wait()
            proxy = self._get_proxy()
            proxy.Hello("Foo")
            proxy.Hello("Bar")

        self._add_client(test1)
        self._add_client(test2)
        self._run_test()

        visited.assert_has_calls([
            mock.call("Visited by Foo."),
            mock.call("Visited by Bar.")
        ])

    def unsubscribed_test(self):
        """Use an unsubscribed DBus signal."""
        self._set_service(ExampleInterface())
        event = Event()
        knocked = Mock()

        def callback():
            knocked("Knocked!")

        def test_1():
            proxy = self._get_proxy()
            proxy.Knocked.connect(callback)
            disconnect_proxy(proxy)
            event.set()

        def test_2():
            event.wait()
            proxy = self._get_proxy()
            proxy.Knock()
            proxy.Knock()
            proxy.Knock()

        self._add_client(test_1)
        self._add_client(test_2)
        self._run_test()

        knocked.assert_not_called()

    def asynchronous_test(self):
        """Call a DBus method asynchronously."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._names, [])
        returned = Mock()

        def callback(call, number):
            returned(number, call())

        def test():
            proxy = self._get_proxy()
            proxy.Hello("Foo", callback=callback, callback_args=(1, ))
            proxy.Hello("Foo", callback=callback, callback_args=(2, ))
            proxy.Hello("Bar", callback=callback, callback_args=(3, ))

        self._add_client(test)
        self._run_test()

        returned.assert_has_calls([
            mock.call(1, "Hello, Foo!"),
            mock.call(2, "Hello, Foo!"),
            mock.call(3, "Hello, Bar!"),
        ])

    def error_test(self):
        """Handle a DBus error."""
        self._set_service(ExampleInterface())
        self.assertEqual(self.service._names, [])
        raised = Mock()

        def callback(call, number):
            try:
                call()
            except ExampleException as e:
                raised(number, str(e))

        def test1():
            proxy = self._get_proxy()
            proxy.Raise("Foo failed!", callback=callback, callback_args=(1, ))
            proxy.Raise("Foo failed!", callback=callback, callback_args=(2, ))
            proxy.Raise("Bar failed!", callback=callback, callback_args=(3, ))

        def test2():
            proxy = self._get_proxy()

            try:
                proxy.Raise("My message")
            except ExampleException as e:
                self.assertEqual(str(e), "My message")
            else:
                self.fail("Exception wasn't raised!")

        self._add_client(test1)
        self._add_client(test2)
        self._run_test()

        raised.assert_has_calls([
            mock.call(1, "Foo failed!"),
            mock.call(2, "Foo failed!"),
            mock.call(3, "Bar failed!"),
        ])

    def properties_changed_test(self):
        self._set_service(ExampleInterface())
        event = Event()
        callback = Mock()

        def test_1():
            proxy = self._get_proxy()
            proxy.PropertiesChanged.connect(callback)
            event.set()

        def test_2():
            event.wait()
            proxy = self._get_proxy()
            proxy.Value = 10

        self._add_client(test_1)
        self._add_client(test_2)
        self._run_test()

        callback.assert_called_once_with(
            "my.testing.Example",
            {"Value": 10},
            ["Name"]
        )
