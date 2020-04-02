#
# Copyright (C) 2020  Red Hat, Inc.
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
import unittest

from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.core.constants import SECRET_TYPE_NONE, \
    SECRET_TYPE_TEXT, SECRET_TYPE_HIDDEN
from pyanaconda.modules.common.structures.secret import SecretData, SecretDataList, hide_secrets, \
    get_public_copy


class SecretDataTestCase(unittest.TestCase):
    """Test DBus structures with secrets."""

    def get_string_test(self):
        """Test the string representation of SecretData."""
        data = SecretData()
        expected = "SecretData(type='NONE', value_set=False)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

        data.set_secret("secret")
        expected = "SecretData(type='TEXT', value_set=True)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

        data.hide_secret()
        expected = "SecretData(type='HIDDEN', value_set=False)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

    def get_structure_test(self):
        """Test the DBus structure with SecretData."""
        data = SecretData()

        self.assertEqual(
            SecretData.to_structure(data),
            {
                'type': get_variant(Str, SECRET_TYPE_NONE),
                'value': get_variant(Str, "")
            }
        )

        data = SecretData.from_structure(
            {
                'type': get_variant(Str, SECRET_TYPE_TEXT),
                'value': get_variant(Str, "secret")
            }
        )

        self.assertEqual(data.type, SECRET_TYPE_TEXT)
        self.assertEqual(data.value, "secret")

    def set_secret_test(self):
        """Test the set_secret method of SecretData."""
        data = SecretData()
        data.set_secret("secret")
        self.assertEqual(data.type, SECRET_TYPE_TEXT)
        self.assertEqual(data.value, "secret")

        data.set_secret(None)
        self.assertEqual(data.type, SECRET_TYPE_NONE)
        self.assertEqual(data.value, "")

    def hide_secret_test(self):
        """Test the hide_secret method of SecretData."""
        data = SecretData()
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_NONE)
        self.assertEqual(data.value, "")

        data.type = SECRET_TYPE_TEXT
        data.value = "secret"
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_HIDDEN)
        self.assertEqual(data.value, "")

        data.type = SECRET_TYPE_HIDDEN
        data.value = "secret"
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_HIDDEN)
        self.assertEqual(data.value, "")


class SecretDataListTestCase(unittest.TestCase):
    """Test DBus structures with lists of secrets."""

    def get_string_test(self):
        """Test the string representation of SecretDataList."""
        data = SecretDataList()
        expected = "SecretDataList(type='NONE', value_set=False)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

        data.set_secret("secret")
        expected = "SecretDataList(type='TEXT', value_set=True)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

        data.hide_secret()
        expected = "SecretDataList(type='HIDDEN', value_set=False)"
        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

    def get_structure_test(self):
        """Test the DBus structure with SecretDataList."""
        data = SecretDataList()

        self.assertEqual(
            SecretDataList.to_structure(data),
            {
                'type': get_variant(Str, SECRET_TYPE_NONE),
                'value': get_variant(List[Str], [])
            }
        )

        data = SecretDataList.from_structure(
            {
                'type': get_variant(Str, SECRET_TYPE_TEXT),
                'value': get_variant(List[Str], ["s1", "s2", "s3"])
            }
        )

        self.assertEqual(data.type, SECRET_TYPE_TEXT)
        self.assertEqual(data.value, ["s1", "s2", "s3"])

    def set_secret_test(self):
        """Test the set_secret method of SecretDataList."""
        data = SecretDataList()
        data.set_secret(["s1", "s2", "s3"])
        self.assertEqual(data.type, SECRET_TYPE_TEXT)
        self.assertEqual(data.value, ["s1", "s2", "s3"])

        data.set_secret(None)
        self.assertEqual(data.type, SECRET_TYPE_NONE)
        self.assertEqual(data.value, [])

    def hide_secret_test(self):
        """Test the hide_secret method of SecretDataList."""
        data = SecretDataList()
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_NONE)
        self.assertEqual(data.value, [])

        data.type = SECRET_TYPE_TEXT
        data.value = ["s1", "s2", "s3"]
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_HIDDEN)
        self.assertEqual(data.value, [])

        data.type = SECRET_TYPE_HIDDEN
        data.value = ["s1", "s2", "s3"]
        data.hide_secret()
        self.assertEqual(data.type, SECRET_TYPE_HIDDEN)
        self.assertEqual(data.value, [])


class DataWithSecretsTestCase(unittest.TestCase):
    """Test DBus structures with secrets."""

    class Data(DBusData):
        def __init__(self):
            self._a = ""
            self._b = SecretData()
            self._c = SecretDataList()

        @property
        def a(self) -> Str:
            return self._a

        @a.setter
        def a(self, value):
            self._a = value

        @property
        def b(self) -> SecretData:
            return self._b

        @b.setter
        def b(self, value):
            self._b = value

        @property
        def c(self) -> SecretDataList:
            return self._c

        @c.setter
        def c(self, value):
            self._c = value

    def get_string_test(self):
        """Test the string representation of complex data."""
        data = self.Data()
        data.a = "a"
        data.b.set_secret("b")
        data.c.set_secret(["c1", "c2", "c3"])

        expected = \
            "Data(" \
            "a='a', " \
            "b=SecretData(type='TEXT', value_set=True), " \
            "c=SecretDataList(type='TEXT', value_set=True))"

        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

        hide_secrets(data)

        expected = \
            "Data(" \
            "a='a', " \
            "b=SecretData(type='HIDDEN', value_set=False), " \
            "c=SecretDataList(type='HIDDEN', value_set=False))"

        self.assertEqual(str(data), expected)
        self.assertEqual(repr(data), expected)

    def hide_secrets_test(self):
        """Test the function hide_secrets."""
        data = self.Data()
        data.a = "a"
        data.b.set_secret("b")
        data.c.set_secret(["c1", "c2", "c3"])

        self.assertEqual(get_native(self.Data.to_structure(data)), {
            "a": "a",
            "b": {"type": SECRET_TYPE_TEXT, "value": "b"},
            "c": {"type": SECRET_TYPE_TEXT, "value": ["c1", "c2", "c3"]},
        })

        hide_secrets(data)

        self.assertEqual(get_native(self.Data.to_structure(data)), {
            "a": "a",
            "b": {"type": SECRET_TYPE_HIDDEN, "value": ""},
            "c": {"type": SECRET_TYPE_HIDDEN, "value": []},
        })

    def get_public_copy_test(self):
        """Test the function hide_secrets."""
        data_1 = self.Data()
        data_1.a = "a"
        data_1.b.set_secret("b")
        data_1.c.set_secret(["c1", "c2", "c3"])
        data_2 = get_public_copy(data_1)

        self.assertIsNot(data_1, data_2)

        self.assertEqual(get_native(self.Data.to_structure(data_1)), {
            "a": "a",
            "b": {"type": SECRET_TYPE_TEXT, "value": "b"},
            "c": {"type": SECRET_TYPE_TEXT, "value": ["c1", "c2", "c3"]},
        })

        self.assertEqual(get_native(self.Data.to_structure(data_2)), {
            "a": "a",
            "b": {"type": SECRET_TYPE_HIDDEN, "value": ""},
            "c": {"type": SECRET_TYPE_HIDDEN, "value": []},
        })
