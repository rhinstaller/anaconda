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
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.typing import get_dbus_type

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


class DBusTypingTests(unittest.TestCase):

    def _compare(self, type_hint, expected_string):
        """Compare generated and expected types."""
        dbus_type = get_dbus_type(type_hint)
        self.assertEqual(dbus_type, expected_string)
        self.assertTrue(GLib.VariantType.string_is_valid(dbus_type))

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


class DBusTypingVariantTests(unittest.TestCase):

    def _test_variant(self, type_hint, expected_string, value):
        """Create a variant."""
        v1 = get_variant(type_hint, value)
        self.assertTrue(isinstance(v1, Variant))
        self.assertEqual(v1.format_string, expected_string)  # pylint: disable=no-member
        self.assertEqual(v1.unpack(), value)

        v2 = Variant(expected_string, value)
        self.assertTrue(v2.equal(v1))

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
