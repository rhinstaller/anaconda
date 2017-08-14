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

        with self.assertRaises(ValueError):
            get_dbus_type(UnknownType)

        with self.assertRaises(ValueError):
            get_dbus_type(List[UnknownType])

        with self.assertRaises(ValueError):
            get_dbus_type(Tuple[Int, Str, UnknownType])

        with self.assertRaises(ValueError):
            get_dbus_type(Dict[Int, UnknownType])

    def invalid_test(self):
        """Test the invalid types."""
        with self.assertRaises(ValueError):
            get_dbus_type(Dict[List[Bool], Bool])

        with self.assertRaises(ValueError):
            get_dbus_type(Dict[Variant, Int])

        with self.assertRaises(ValueError):
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

    @unittest.skip("Requires mypy to be setup.")
    def mypy_test(self):
        """Test types with mypy."""
        from mypy import api  # pylint: disable=import-error
        out, err, res = api.run(["-c", mypy_script])
        self.assertEqual(res, 0, msg=out + err)

mypy_script = """
from pyanaconda.dbus.typing import *

a = True        # type: Bool
b = 1.0         # type: Double
c = ""          # type: Str

d = 1           # type: Int
e = Byte(1)     # type: Byte
f = Int16(1)    # type: Int16
g = UInt16(1)   # type: UInt16
h = Int32(1)    # type: Int32
i = UInt32(1)   # type: UInt32
j = Int64(1)    # type: Int64
k = UInt64(1)   # type: UInt64

l = open("/tmp/123")  # type: File
m = ObjPath("/com/mycompany/c5yo817y0c1y1c5b")  # type: ObjPath

n = (1, "a")    # type: Tuple[Int, Str]
o = {1: "a"}    # type: Dict[Int, Str]
p = [1, 2, 3]   # type: List[Int]

va = True        # type: Variant
vb = 1.0         # type: Variant
vc = ""          # type: Variant

vd = 1           # type: Variant
ve = Byte(1)     # type: Variant
vf = Int16(1)    # type: Variant
vg = UInt16(1)   # type: Variant
vh = Int32(1)    # type: Variant
vi = UInt32(1)   # type: Variant
vj = Int64(1)    # type: Variant
vk = UInt64(1)   # type: Variant

vl = open("/tmp/123")  # type: Variant
vm = ObjPath("/com/mycompany/c5yo817y0c1y1c5b")  # type: Variant

vn = (1, "a")    # type: Variant
vo = {1: "a"}    # type: Variant
vp = [1, 2, 3]   # type: Variant
"""
