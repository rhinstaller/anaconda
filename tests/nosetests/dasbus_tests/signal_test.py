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
from unittest.mock import Mock

from dasbus.server.interface import dbus_signal
from dasbus.signal import Signal


class DBusSignalTestCase(unittest.TestCase):
    """Test DBus signals."""

    def create_signal_test(self):
        """Create a signal."""
        class Interface(object):

            @dbus_signal
            def Signal(self):
                pass

        interface = Interface()
        signal = interface.Signal
        self.assertIsInstance(signal, Signal)
        self.assertTrue(hasattr(interface, "__dbus_signal_signal"))
        self.assertEqual(getattr(interface, "__dbus_signal_signal"), signal)

    def emit_signal_test(self):
        """Emit a signal."""
        class Interface(object):

            @dbus_signal
            def Signal(self, a, b, c):
                pass

        interface = Interface()
        signal = interface.Signal

        callback = Mock()
        signal.connect(callback)  # pylint: disable=no-member

        signal.emit(1, 2, 3)  # pylint: disable=no-member
        callback.assert_called_once_with(1, 2, 3)
        callback.reset_mock()

        signal.emit(4, 5, 6)  # pylint: disable=no-member
        callback.assert_called_once_with(4, 5, 6)
        callback.reset_mock()

    def disconnect_signal_test(self):
        """Disconnect a signal."""
        class Interface(object):

            @dbus_signal
            def Signal(self):
                pass

        interface = Interface()
        callback = Mock()
        interface.Signal.connect(callback)  # pylint: disable=no-member

        interface.Signal()
        callback.assert_called_once_with()
        callback.reset_mock()

        interface.Signal.disconnect(callback)  # pylint: disable=no-member
        interface.Signal()
        callback.assert_not_called()

        interface.Signal.connect(callback)  # pylint: disable=no-member
        interface.Signal.disconnect()  # pylint: disable=no-member
        interface.Signal()
        callback.assert_not_called()

    def signals_test(self):
        """Test a class with two signals."""
        class Interface(object):

            @dbus_signal
            def Signal1(self):
                pass

            @dbus_signal
            def Signal2(self):
                pass

        interface = Interface()
        signal1 = interface.Signal1
        signal2 = interface.Signal2

        self.assertNotEqual(signal1, signal2)

        callback1 = Mock()
        signal1.connect(callback1)  # pylint: disable=no-member

        callback2 = Mock()
        signal2.connect(callback2)  # pylint: disable=no-member

        signal1.emit()  # pylint: disable=no-member
        callback1.assert_called_once_with()
        callback2.assert_not_called()
        callback1.reset_mock()

        signal2.emit()  # pylint: disable=no-member
        callback1.assert_not_called()
        callback2.assert_called_once_with()

    def instances_test(self):
        """Test two instances of the class with a signal."""
        class Interface(object):

            @dbus_signal
            def Signal(self):
                pass

        interface1 = Interface()
        signal1 = interface1.Signal

        interface2 = Interface()
        signal2 = interface2.Signal
        self.assertNotEqual(signal1, signal2)

        callback = Mock()
        signal1.connect(callback)  # pylint: disable=no-member

        callback2 = Mock()
        signal2.connect(callback2)  # pylint: disable=no-member

        signal1.emit()  # pylint: disable=no-member
        callback.assert_called_once_with()
        callback2.assert_not_called()
