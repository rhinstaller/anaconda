#
# Copyright (C) 2018  Red Hat, Inc.
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

from mock import Mock, call

from dasbus.server.interface import dbus_interface
from dasbus.server.property import PropertiesInterface, emits_properties_changed, \
    PropertiesException, PropertiesChanges
from dasbus.signal import Signal
from dasbus.specification import DBusSpecificationError
from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.server.template import InterfaceTemplate


class DBusPropertySpecificationTestCase(unittest.TestCase):
    """Test generating properties from DBus specification."""

    def properties_mapping_test(self):
        """Test properties mapping."""

        class Interface(object):
            __dbus_xml__ = '''
            <node>
                <interface name="A">
                    <property name="A1" type="i" access="readwrite" />
                    <property name="A2" type="d" access="read" />
                    <property name="A3" type="s" access="write" />
                </interface>
                <interface name="B">
                    <property name="B1" type="i" access="readwrite" />
                    <property name="B2" type="d" access="read" />
                    <property name="B3" type="s" access="write" />
                </interface>
                <interface name="C">
                    <property name="C1" type="i" access="readwrite" />
                    <property name="C2" type="d" access="read" />
                    <property name="C3" type="s" access="write" />
                </interface>
            </node>
            '''

        changes = PropertiesChanges(Interface())
        mapping = {
            member.name: member.interface_name
            for member in changes._properties_specs.values()
        }
        expected_mapping = {
            "A1": "A", "B1": "B", "C1": "C",
            "A2": "A", "B2": "B", "C2": "C",
            "A3": "A", "B3": "B", "C3": "C",
        }

        self.assertDictEqual(mapping, expected_mapping)

    def invalid_properties_mapping_test(self):
        """Test for invalid properties."""

        class Interface(object):
            __dbus_xml__ = '''
            <node>
                <interface name="A">
                    <property name="A1" type="i" access="readwrite" />
                    <property name="A2" type="d" access="read" />
                    <property name="A3" type="s" access="write" />
                </interface>
                <interface name="B">
                    <property name="A1" type="i" access="readwrite" />
                    <property name="B2" type="d" access="read" />
                    <property name="B3" type="s" access="write" />
                </interface>
            </node>
            '''

        with self.assertRaises(DBusSpecificationError):
            PropertiesChanges(Interface())


class DBusPropertyTestCase(unittest.TestCase):
    """Test support for DBus properties."""

    @dbus_interface("I1")
    class Test1(PropertiesInterface):

        @property
        def A(self) -> Int:
            return 1

        @property
        def B(self) -> Int:
            return 2

    def report_changed_test(self):
        """Test reporting changed properties."""
        test1 = self.Test1()

        callback = Mock()
        test1.PropertiesChanged.connect(callback)

        test1.flush_changes()
        callback.assert_not_called()

        test1.report_changed_property("A")
        test1.flush_changes()
        callback.assert_called_once_with("I1", {
            "A": get_variant(Int, 1)
        }, [])
        callback.reset_mock()

        test1.report_changed_property("B")
        test1.flush_changes()
        callback.assert_called_once_with("I1", {
            "B": get_variant(Int, 2)
        }, [])
        callback.reset_mock()

        test1.report_changed_property("B")
        test1.report_changed_property("A")
        test1.flush_changes()
        callback.assert_called_once_with("I1", {
            "A": get_variant(Int, 1),
            "B": get_variant(Int, 2)
        }, [])
        callback.reset_mock()

    @dbus_interface("I2")
    class Test2(PropertiesInterface):

        def __init__(self):
            super().__init__()
            self._a = 1

        @property
        def a(self):
            return self._a

        @a.setter
        def a(self, a):
            self._a = a
            self.report_changed_property("A")

        @property
        def A(self) -> Int:
            return self.a

        @emits_properties_changed
        def SetA(self, a: Int):
            self.a = a

        @emits_properties_changed
        def SetADirectly(self, a: Int):
            self._a = a

        def SetANoSignal(self, a: Int):
            self.a = a

        def DoNothing(self):
            pass

    def emit_changed_test(self):
        """Test emitting changed properties."""
        test2 = self.Test2()

        callback = Mock()
        test2.PropertiesChanged.connect(callback)

        self.assertEqual(test2.A, 1)

        test2.DoNothing()
        self.assertEqual(test2.A, 1)
        callback.assert_not_called()

        test2.SetA(10)
        self.assertEqual(test2.A, 10)
        callback.assert_called_once_with("I2", {
            "A": get_variant(Int, 10)
        }, [])
        callback.reset_mock()

        test2.SetA(1000)
        self.assertEqual(test2.A, 1000)
        callback.assert_called_once_with("I2", {
            "A": get_variant(Int, 1000)
        }, [])
        callback.reset_mock()

        test2.SetADirectly(20)
        self.assertEqual(test2.A, 20)
        callback.assert_not_called()
        callback.reset_mock()

        test2.flush_changes()
        callback.assert_not_called()

        test2.SetANoSignal(200)
        self.assertEqual(test2.A, 200)
        callback.assert_not_called()

        test2.flush_changes()
        callback.assert_called_once_with("I2", {
            "A": get_variant(Int, 200)
        }, [])

    @dbus_interface("I3")
    class Test3(InterfaceTemplate):

        def connect_signals(self):
            super().connect_signals()
            self.implementation.module_properties_changed.connect(self.flush_changes)
            self.watch_property("A", self.implementation.a_changed)
            self.watch_property("B", self.implementation.b_changed)

        @property
        def A(self) -> Int:
            return self.implementation.a

        @emits_properties_changed
        def SetA(self, a: Int):
            self.implementation.set_a(a)

        @property
        def B(self) -> Int:
            return self.implementation.b

        @B.setter
        @emits_properties_changed
        def B(self, b: Int):
            self.implementation.b = b

    class Test3Implementation(object):

        def __init__(self):
            self.module_properties_changed = Signal()
            self.a_changed = Signal()
            self.b_changed = Signal()

            self._a = 1
            self._b = 2

        @property
        def a(self):
            return self._a

        def set_a(self, a):
            self._a = a
            self.a_changed.emit()

        @property
        def b(self):
            return self._b

        @b.setter
        def b(self, b):
            self._b = b
            self.b_changed.emit()

        def do_external_changes(self, a, b):
            self.set_a(a)
            self.b = b

        def do_secret_changes(self, a, b):
            self._a = a
            self._b = b

    def template_test(self):
        """Test the template with support for properties."""
        test3implementation = self.Test3Implementation()
        test3 = self.Test3(test3implementation)

        callback = Mock()
        test3.PropertiesChanged.connect(callback)

        self.assertEqual(test3.A, 1)
        self.assertEqual(test3.B, 2)

        test3.SetA(10)
        self.assertEqual(test3.A, 10)
        callback.assert_called_once_with("I3", {
            "A": get_variant(Int, 10)
        }, [])
        callback.reset_mock()

        test3.B = 20
        self.assertEqual(test3.B, 20)
        callback.assert_called_once_with("I3", {
            "B": get_variant(Int, 20)
        }, [])
        callback.reset_mock()

        test3implementation.do_external_changes(100, 200)
        self.assertEqual(test3.A, 100)
        self.assertEqual(test3.B, 200)
        callback.assert_not_called()

        test3implementation.module_properties_changed.emit()
        callback.assert_called_once_with("I3", {
            "A": get_variant(Int, 100),
            "B": get_variant(Int, 200)
        }, [])
        callback.reset_mock()

        test3implementation.do_secret_changes(1000, 2000)
        self.assertEqual(test3.A, 1000)
        self.assertEqual(test3.B, 2000)
        callback.assert_not_called()

        test3implementation.module_properties_changed.emit()
        callback.assert_not_called()

    @dbus_interface("I4")
    class Test4(InterfaceTemplate):

        def connect_signals(self):
            super().connect_signals()
            self.implementation.module_properties_changed.connect(self.flush_changes)
            self.watch_property("A", self.implementation.a_changed)

        @property
        def A(self) -> Int:
            return self.implementation.a

        @emits_properties_changed
        def SetA(self, a: Int):
            self.implementation.set_a(a)

        @emits_properties_changed
        def DoChanges(self, a: Int, b: Int):
            self.implementation.do_external_changes(a, b)

    @dbus_interface("I5")
    class Test5(Test4):

        def connect_signals(self):
            super().connect_signals()
            self.watch_property("B", self.implementation.b_changed)

        @property
        def B(self) -> Int:
            return self.implementation.b

        @B.setter
        @emits_properties_changed
        def B(self, b: Int):
            self.implementation.b = b

    class Test5Implementation(Test3Implementation):
        pass

    def multiple_interfaces_test(self):
        """Test template with multiple inheritance."""
        test5implementation = self.Test5Implementation()
        test5 = self.Test5(test5implementation)

        callback = Mock()
        test5.PropertiesChanged.connect(callback)

        self.assertEqual(test5.A, 1)
        self.assertEqual(test5.B, 2)

        test5.SetA(10)
        self.assertEqual(test5.A, 10)
        callback.assert_called_once_with("I4", {
            "A": get_variant(Int, 10)
        }, [])
        callback.reset_mock()

        test5.B = 20
        self.assertEqual(test5.B, 20)
        callback.assert_called_once_with("I5", {
            "B": get_variant(Int, 20)
        }, [])
        callback.reset_mock()

        test5.DoChanges(1, 2)
        self.assertEqual(test5.A, 1)
        self.assertEqual(test5.B, 2)
        callback.assert_has_calls([
            call("I4", {"A": get_variant(Int, 1)}, []),
            call("I5", {"B": get_variant(Int, 2)}, [])
        ], any_order=True)
        callback.reset_mock()

        test5implementation.do_external_changes(100, 200)
        self.assertEqual(test5.A, 100)
        self.assertEqual(test5.B, 200)
        callback.assert_not_called()

        test5implementation.module_properties_changed.emit()
        callback.assert_has_calls([
            call("I4", {"A": get_variant(Int, 100)}, []),
            call("I5", {"B": get_variant(Int, 200)}, [])
        ], any_order=True)
        callback.reset_mock()

        test5implementation.do_secret_changes(1000, 2000)
        self.assertEqual(test5.A, 1000)
        self.assertEqual(test5.B, 2000)
        callback.assert_not_called()

        test5implementation.module_properties_changed.emit()
        callback.assert_not_called()

    class Test6(PropertiesInterface):
        pass

    def invalid_class_test(self):
        """Test the properties interface with invalid class."""
        with self.assertRaises(DBusSpecificationError):
            self.Test6()

    @dbus_interface("I7")
    class Test7(PropertiesInterface):
        pass

    def invalid_property_test(self):
        """Test the properties interface with invalid property."""
        test7 = self.Test7()

        with self.assertRaises(PropertiesException):
            test7.report_changed_property("A")

    @dbus_interface("I8")
    class Test8(InterfaceTemplate):
        pass

    class Test8Implementation(object):
        pass

    def invalid_property_template_test(self):
        """Test the template with invalid property."""
        test8implementation = self.Test8Implementation()
        test8 = self.Test8(test8implementation)
        signal = Mock()

        with self.assertRaises(PropertiesException):
            test8.watch_property("A", signal)

        signal.connect.assert_not_called()
