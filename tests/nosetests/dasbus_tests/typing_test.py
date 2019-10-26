#
# Copyright (C) 2017  Red Hat, Inc.
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

from typing import Set

from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.typing import get_dbus_type

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


class DBusTypingTests(unittest.TestCase):

    def _compare(self, type_hint, expected_string):
        """Compare generated and expected types."""
        # Generate a type string.
        dbus_type = get_dbus_type(type_hint)
        self.assertEqual(dbus_type, expected_string)
        self.assertTrue(GLib.VariantType.string_is_valid(dbus_type))

        # Create a variant type from a type hint.
        variant_type = get_variant_type(type_hint)
        self.assertIsInstance(variant_type, GLib.VariantType)
        self.assertEqual(variant_type.dup_string(), expected_string)

        expected_type = GLib.VariantType.new(expected_string)
        self.assertTrue(expected_type.equal(variant_type))

        # Create a variant type from a type string.
        variant_type = get_variant_type(expected_string)
        self.assertIsInstance(variant_type, GLib.VariantType)
        self.assertTrue(expected_type.equal(variant_type))

    def unknown_test(self):
        """Test the unknown type."""

        class UnknownType:
            pass

        with self.assertRaises(TypeError):
            get_dbus_type(UnknownType)

        with self.assertRaises(TypeError):
            get_dbus_type(List[UnknownType])

        with self.assertRaises(TypeError):
            get_dbus_type(Tuple[Int, Str, UnknownType])

        with self.assertRaises(TypeError):
            get_dbus_type(Dict[Int, UnknownType])

    def invalid_test(self):
        """Test the invalid types."""
        with self.assertRaises(TypeError):
            get_dbus_type(Dict[List[Bool], Bool])

        with self.assertRaises(TypeError):
            get_dbus_type(Dict[Variant, Int])

        with self.assertRaises(TypeError):
            get_dbus_type(Tuple[Int, Double, Dict[Tuple[Int, Int], Bool]])

        with self.assertRaises(TypeError):
            get_dbus_type(Set[Int])

    def simple_test(self):
        """Test simple types."""
        self._compare(int, "i")
        self._compare(bool, "b")
        self._compare(float, "d")
        self._compare(str, "s")

    def basic_test(self):
        """Test basic types."""
        self._compare(Int, "i")
        self._compare(Bool, "b")
        self._compare(Double, "d")
        self._compare(Str, "s")
        self._compare(ObjPath, "o")
        self._compare(File, "h")
        self._compare(Variant, "v")

    def int_test(self):
        """Test integer types."""
        self._compare(Byte, "y")
        self._compare(Int16, "n")
        self._compare(UInt16, "q")
        self._compare(Int32, "i")
        self._compare(UInt32, "u")
        self._compare(Int64, "x")
        self._compare(UInt64, "t")

    def container_test(self):
        """Test container types."""
        self._compare(Tuple[Bool], "(b)")
        self._compare(Tuple[Int, Str], "(is)")
        self._compare(Tuple[File, Variant, Double], "(hvd)")

        self._compare(List[Int], "ai")
        self._compare(List[Bool], "ab")
        self._compare(List[File], "ah")
        self._compare(List[ObjPath], "ao")

        self._compare(Dict[Str, Int], "a{si}")
        self._compare(Dict[Int, Bool], "a{ib}")

    def alias_test(self):
        """Test type aliases."""
        AliasType = List[Double]
        self._compare(Dict[Str, AliasType], "a{sad}")

    def depth_test(self):
        """Test difficult type structures."""
        self._compare(Tuple[Int, Tuple[Str, Str]], "(i(ss))")
        self._compare(Tuple[Tuple[Tuple[Int]]], "(((i)))")
        self._compare(Tuple[Bool, Tuple[Tuple[Int], Str]], "(b((i)s))")

        self._compare(List[List[List[Int]]], "aaai")
        self._compare(List[Tuple[Dict[Str, Int]]], "a(a{si})")
        self._compare(List[Dict[Str, Tuple[File, Variant]]], "aa{s(hv)}")

        self._compare(Dict[Str, List[Bool]], "a{sab}")
        self._compare(Dict[Str, Tuple[Int, Int, Double]], "a{s(iid)}")
        self._compare(Dict[Str, Tuple[Int, Int, Dict[Int, Str]]], "a{s(iia{is})}")

    def base_type_test(self):
        """Test the base type checks."""
        self.assertEqual(is_base_type(Int, Int), True)
        self.assertEqual(is_base_type(UInt16, UInt16), True)
        self.assertEqual(is_base_type(Variant, Variant), True)

        self.assertEqual(is_base_type(Int, Bool), False)
        self.assertEqual(is_base_type(Bool, List), False)
        self.assertEqual(is_base_type(UInt16, Dict), False)
        self.assertEqual(is_base_type(UInt16, Int), False)
        self.assertEqual(is_base_type(Variant, Tuple), False)

        self.assertEqual(is_base_type(List[Int], List), True)
        self.assertEqual(is_base_type(List[Bool], List), True)
        self.assertEqual(is_base_type(List[Variant], List), True)

        self.assertEqual(is_base_type(Tuple[Int], Tuple), True)
        self.assertEqual(is_base_type(Tuple[Bool], Tuple), True)
        self.assertEqual(is_base_type(Tuple[Variant], Tuple), True)

        self.assertEqual(is_base_type(Dict[Str, Int], Dict), True)
        self.assertEqual(is_base_type(Dict[Str, Bool], Dict), True)
        self.assertEqual(is_base_type(Dict[Str, Variant], Dict), True)

        self.assertEqual(is_base_type(List[Int], Tuple), False)
        self.assertEqual(is_base_type(Tuple[Bool], Dict), False)
        self.assertEqual(is_base_type(Dict[Str, Variant], List), False)

    def base_class_test(self):
        """Test the base class checks."""
        class Data(object):
            pass

        class DataA(Data):
            pass

        class DataB(Data):
            pass

        self.assertEqual(is_base_type(Data, Data), True)
        self.assertEqual(is_base_type(DataA, Data), True)
        self.assertEqual(is_base_type(DataB, Data), True)

        self.assertEqual(is_base_type(Data, DataA), False)
        self.assertEqual(is_base_type(Data, DataB), False)
        self.assertEqual(is_base_type(DataA, DataB), False)
        self.assertEqual(is_base_type(DataB, DataA), False)

        self.assertEqual(is_base_type(List[Data], List), True)
        self.assertEqual(is_base_type(Tuple[DataA], Tuple), True)
        self.assertEqual(is_base_type(Dict[Str, DataB], Dict), True)


class DBusTypingVariantTests(unittest.TestCase):

    def _test_variant(self, type_hint, expected_string, value):
        """Create a variant."""
        # Create a variant from a type hint.
        v1 = get_variant(type_hint, value)
        self.assertTrue(isinstance(v1, Variant))
        self.assertEqual(v1.format_string, expected_string)  # pylint: disable=no-member
        self.assertEqual(v1.unpack(), value)

        v2 = Variant(expected_string, value)
        self.assertTrue(v2.equal(v1))

        self.assertEqual(get_native(v1), value)
        self.assertEqual(get_native(v1), get_native(v2))
        self.assertEqual(get_native(value), value)

        # Create a variant from a type string.
        v3 = get_variant(expected_string, value)
        self.assertTrue(isinstance(v3, Variant))
        self.assertTrue(v2.equal(v3))

    def variant_invalid_test(self):
        """Test invalid variants."""

        class UnknownType:
            pass

        with self.assertRaises(TypeError):
            get_variant(UnknownType, 1)

        with self.assertRaises(TypeError):
            get_variant(List[Int], True)

    def variant_basic_test(self):
        """Test variants with basic types."""
        self._test_variant(Int, "i", 1)
        self._test_variant(Bool, "b", True)
        self._test_variant(Double, "d", 1.0)
        self._test_variant(Str, "s", "Hi!")
        self._test_variant(ObjPath, "o", "/org/something")

    def variant_int_test(self):
        """Test variants with integer types."""
        self._test_variant(Int16, "n", 2)
        self._test_variant(UInt16, "q", 3)
        self._test_variant(Int32, "i", 4)
        self._test_variant(UInt32, "u", 5)
        self._test_variant(Int64, "x", 6)
        self._test_variant(UInt64, "t", 7)

    def variant_container_test(self):
        """Test variants with container types."""
        self._test_variant(Tuple[Bool], "(b)", (False,))
        self._test_variant(Tuple[Int, Str], "(is)", (0, "zero"))

        self._test_variant(List[Int], "ai", [1, 2, 3])
        self._test_variant(List[Bool], "ab", [True, False, True])

        self._test_variant(Dict[Str, Int], "a{si}", {"a": 1, "b": 2})
        self._test_variant(Dict[Int, Bool], "a{ib}", {1: True, 2: False})

    def variant_alias_test(self):
        """Test variants with type aliases."""
        AliasType = List[Double]
        self._test_variant(Dict[Str, AliasType], "a{sad}", {"test": [1.1, 2.2]})

    def _test_native(self, variants, values):
        """Test native values of variants."""
        for variant, value in zip(variants, values):
            self.assertEqual(get_native(variant), value)

        self.assertEqual(get_native(tuple(variants)), tuple(values))
        self.assertEqual(get_native(list(variants)), list(values))
        self.assertEqual(get_native(dict(enumerate(variants))), dict(enumerate(values)))

    def basic_native_test(self):
        """Test get_native with basic variants."""
        self._test_native(
            [
                get_variant(Double, 1.2),
                get_variant(List[Int], [0, -1]),
                get_variant(Tuple[Bool, Bool], (True, False)),
                get_variant(Dict[Str, Int], {"key": 0}),
            ],
            [
                1.2,
                [0, -1],
                (True, False),
                {"key": 0}
            ]
        )

    def complex_native_test(self):
        """Test get_native with complex variants."""
        self._test_native(
            [
                get_variant(Variant, get_variant(Double, 1.2)),
                get_variant(List[Variant], [get_variant(Int, 0), get_variant(Int, -1)]),
                get_variant(Tuple[Variant, Bool], (get_variant(Bool, True), False)),
                get_variant(Dict[Str, Variant], {"key": get_variant(Int, 0)})
            ],
            [
                1.2,
                [0, -1],
                (True, False),
                {"key": 0}
            ]
        )
