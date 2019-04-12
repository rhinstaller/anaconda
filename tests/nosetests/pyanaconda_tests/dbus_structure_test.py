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

from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.structure import DBusData, DBusStructureError, generate_string_from_data


class DBusStructureTestCase(unittest.TestCase):
    """Test the DBus structure support."""

    def empty_structure_test(self):
        with self.assertRaises(DBusStructureError) as cm:
            class NoData(DBusData):
                pass

            NoData()

        self.assertEqual(str(cm.exception), "No fields found.")

    def readonly_structure_test(self):
        with self.assertRaises(DBusStructureError) as cm:
            class ReadOnlyData(DBusData):
                @property
                def x(self) -> Int:
                    return 1

            ReadOnlyData()

        self.assertEqual(str(cm.exception), "Field 'x' cannot be set.")

    def writeonly_structure_test(self):
        with self.assertRaises(DBusStructureError) as cm:
            class WriteOnlyData(DBusData):
                def __init__(self):
                    self._x = 0

                def set_x(self, x):
                    self._x = x

                x = property(None, set_x)

            WriteOnlyData()

        self.assertEqual(str(cm.exception), "Field 'x' cannot be get.")

    def no_type_structure_test(self):
        with self.assertRaises(DBusStructureError) as cm:
            class NoTypeData(DBusData):
                def __init__(self):
                    self._x = 0

                @property
                def x(self):
                    return self._x

                @x.setter
                def x(self, x):
                    self._x = x

            NoTypeData()

        self.assertEqual(str(cm.exception), "Field 'x' has unknown type.")

    class SkipData(DBusData):

        class_attribute = 1

        def __init__(self):
            self._x = 0
            self._y = 1

        @property
        def x(self) -> Int:
            return self._x

        @property
        def _private_property(self):
            return 1

        @x.setter
        def x(self, x):
            self._x = x

        def method(self):
            pass

    def skip_members_test(self):
        data = self.SkipData()
        structure = self.SkipData.to_structure(data)
        self.assertEqual(structure, {'x': get_variant(Int, 0)})

        data = self.SkipData.from_structure({'x': 10})
        self.assertEqual(data.x, 10)

    class SimpleData(DBusData):

        def __init__(self):
            self._x = 0

        @property
        def x(self) -> Int:
            return self._x

        @x.setter
        def x(self, x):
            self._x = x

    def get_simple_structure_test(self):
        data = self.SimpleData()
        self.assertEqual(data.x, 0)

        structure = self.SimpleData.to_structure(data)
        self.assertEqual(structure, {'x': get_variant(Int, 0)})

        data.x = 10
        self.assertEqual(data.x, 10)

        structure = self.SimpleData.to_structure(data)
        self.assertEqual(structure, {'x': get_variant(Int, 10)})

    def get_simple_structure_list_test(self):
        d1 = self.SimpleData()
        d1.x = 1

        d2 = self.SimpleData()
        d2.x = 2

        d3 = self.SimpleData()
        d3.x = 3

        structures = self.SimpleData.to_structure_list([d1, d2, d3])

        self.assertEqual(structures, [
            {'x': get_variant(Int, 1)},
            {'x': get_variant(Int, 2)},
            {'x': get_variant(Int, 3)}
        ])

    def apply_simple_structure_test(self):
        data = self.SimpleData()
        self.assertEqual(data.x, 0)

        structure = {'x': 10}
        data = self.SimpleData.from_structure(structure)

        self.assertEqual(data.x, 10)

    def apply_simple_invalid_structure_test(self):
        with self.assertRaises(DBusStructureError) as cm:
            self.SimpleData.from_structure({'y': 10})

        self.assertEqual(str(cm.exception), "Field 'y' doesn't exist.")

    def apply_simple_structure_list_test(self):
        s1 = {'x': 1}
        s2 = {'x': 2}
        s3 = {'x': 3}

        data = self.SimpleData.from_structure_list([s1, s2, s3])

        self.assertEqual(len(data), 3)
        self.assertEqual(data[0].x, 1)
        self.assertEqual(data[1].x, 2)
        self.assertEqual(data[2].x, 3)

    class OtherData(DBusData):

        def __init__(self):
            self._x = 0

        @property
        def x(self) -> Int:
            return self._x

        @x.setter
        def x(self, x):
            self._x = x

    def get_structure_from_invalid_type_test(self):
        data = self.OtherData()

        with self.assertRaises(TypeError) as cm:
            self.SimpleData.to_structure(data)

        self.assertEqual(str(cm.exception), "Invalid type 'OtherData'.")

    def apply_structure_with_invalid_type_test(self):
        structure = ["x"]

        with self.assertRaises(TypeError) as cm:
            self.SimpleData.from_structure(structure)

        self.assertEqual(str(cm.exception), "Invalid type 'list'.")

    class ComplicatedData(DBusData):

        def __init__(self):
            self._very_long_property_name = ""
            self._bool_list = []
            self._dictionary = {}

        @property
        def dictionary(self) -> Dict[Int, Str]:
            return self._dictionary

        @dictionary.setter
        def dictionary(self, value):
            self._dictionary = value

        @property
        def bool_list(self) -> List[Bool]:
            return self._bool_list

        @bool_list.setter
        def bool_list(self, value):
            self._bool_list = value

        @property
        def very_long_property_name(self) -> Str:
            return self._very_long_property_name

        @very_long_property_name.setter
        def very_long_property_name(self, value):
            self._very_long_property_name = value

    def get_complicated_structure_test(self):
        data = self.ComplicatedData()
        data.dictionary = {1: "1", 2: "2"}
        data.bool_list = [True, False, False]
        data.very_long_property_name = "My String Value"

        self.assertEqual(
            {
                'dictionary': get_variant(Dict[Int, Str], {1: "1", 2: "2"}),
                'bool-list': get_variant(List[Bool], [True, False, False]),
                'very-long-property-name': get_variant(Str, "My String Value")
            },
            self.ComplicatedData.to_structure(data)
        )

    def apply_complicated_structure_test(self):
        data = self.ComplicatedData.from_structure(
            {
                'dictionary': {1: "1", 2: "2"},
                'bool-list': [True, False, False],
                'very-long-property-name': "My String Value"
            }
        )

        self.assertEqual(data.dictionary, {1: "1", 2: "2"})
        self.assertEqual(data.bool_list, [True, False, False])
        self.assertEqual(data.very_long_property_name, "My String Value")

    class StringData(DBusData):

        def __init__(self):
            self._a = 1
            self._b = ""
            self._c = []
            self._d = []

        @property
        def a(self) -> Int:
            return self._a

        @a.setter
        def a(self, value):
            self._a = value

        @property
        def b(self) -> Str:
            return self._b

        @b.setter
        def b(self, value):
            self._b = value

        @property
        def c(self) -> List[Bool]:
            return self._c

        @c.setter
        def c(self, value):
            self._c = value

    def string_representation_test(self):
        data = self.StringData()

        expected = "StringData(a=1, b='', c=[])"
        self.assertEqual(expected, repr(data))
        self.assertEqual(expected, str(data))

        data.a = 123
        data.b = "HELLO"
        data.c = [True, False]

        expected = "StringData(a=123, b='HELLO', c=[True, False])"
        self.assertEqual(expected, repr(data))
        self.assertEqual(expected, str(data))

    class AdvancedStringData(DBusData):

        def __init__(self):
            self._a = ""
            self._b = ""
            self._c = ""

        @property
        def a(self) -> Str:
            return self._a

        @a.setter
        def a(self, value):
            self._a = value

        @property
        def b(self) -> Str:
            return self._b

        @b.setter
        def b(self, value):
            self._b = value

        @property
        def c(self) -> Str:
            return self._c

        @c.setter
        def c(self, value):
            self._c = value

        def __repr__(self):
            return generate_string_from_data(
                obj=self,
                skip=["b"],
                add=["b_is_set={}".format(bool(self.b))]
            )

    def advanced_string_representation_test(self):
        data = self.AdvancedStringData()

        expected = "AdvancedStringData(a='', b_is_set=False, c='')"
        self.assertEqual(expected, repr(data))
        self.assertEqual(expected, str(data))

        data.a = "A"
        data.b = "B"
        data.c = "C"

        expected = "AdvancedStringData(a='A', b_is_set=True, c='C')"
        self.assertEqual(expected, repr(data))
        self.assertEqual(expected, str(data))
