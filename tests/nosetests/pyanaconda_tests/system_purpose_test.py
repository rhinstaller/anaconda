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

import unittest
import tempfile
import os

from pyanaconda.modules.subscription import system_purpose

VALID_FIELDS_FILE_NAME = "valid_fields.json"
VALID_FIELDS_JSON = """
{
    "role": [
      "AAA Desktop",
      "BBB Server",
      "CCC workstation",
      "DDD super hypernode"
    ],
    "service_level_agreement": [
      "Hyper",
      "Super",
      "Reasonable Effort"
    ],
    "usage": [
      "Safe",
      "Cookie Factory",
      "Apocalypse Recovery"
    ]
}"""

class SystemPurposeTests(unittest.TestCase):

    def get_valid_fields_test(self):
        """Test parsing of the valid_fields.json file."""
        # try to open file that does not exist
        with tempfile.TemporaryDirectory() as tempdir_path:
            no_file_path = os.path.join(tempdir_path, VALID_FIELDS_FILE_NAME)
            # the result should be three empty lists
            role, sla, usage = system_purpose.get_valid_fields(valid_fields_file_path=no_file_path)
            self.assertListEqual([role, sla, usage], [[],[],[]])

        # try to parse a valid valid fields file
        with tempfile.NamedTemporaryFile(mode="w+t") as valid_fields_json:
            valid_fields_json.write(VALID_FIELDS_JSON)
            valid_fields_json.flush()
            role, sla, usage = system_purpose.get_valid_fields(valid_fields_file_path=valid_fields_json.name)
            self.assertListEqual(role, ["AAA Desktop", "BBB Server", "CCC workstation", "DDD super hypernode"])
            self.assertListEqual(sla, ["Hyper", "Super", "Reasonable Effort"])
            self.assertListEqual(usage, ["Safe", "Cookie Factory", "Apocalypse Recovery"])

    def normalize_field_test(self):
        """Test system purpose field normalization."""
        self.assertEqual(system_purpose.normalize_field("aaa"), "aaa")
        self.assertEqual(system_purpose.normalize_field("AAA"), "aaa")
        self.assertEqual(system_purpose.normalize_field(" AAA "), "aaa")
        self.assertEqual(system_purpose.normalize_field(" AAA BBB "), "aaa bbb")
        self.assertEqual(system_purpose.normalize_field(" AbC deF "), "abc def")

    def match_field_test(self):
        """Test system purpose field matching works as expected."""
        # should not match
        self.assertIsNone(system_purpose.match_field("A", ["B"]))
        self.assertIsNone(system_purpose.match_field("A-B", ["A B"]))
        self.assertIsNone(system_purpose.match_field("A_B", ["A B"]))
        self.assertIsNone(system_purpose.match_field("A_B", ["A-B"]))
        # should match
        self.assertEqual(system_purpose.match_field("a", ["a"]), "a")
        self.assertEqual(system_purpose.match_field("A", ["a"]), "a")
        self.assertEqual(system_purpose.match_field("a", ["A"]), "A")
        self.assertEqual(system_purpose.match_field(" a ", ["A"]), "A")
        self.assertEqual(system_purpose.match_field("a", [" A "]), " A ")
        self.assertEqual(system_purpose.match_field("a B cd ", ["A b CD"]), "A b CD")
        # match from multiple options
        self.assertEqual(system_purpose.match_field("A", ["B", "c", "def", "A"]), "A")
        self.assertEqual(system_purpose.match_field("A", ["B", "c", "def", "A", "z", "A"]), "A")
        self.assertEqual(system_purpose.match_field("a", ["A", "A"]), "A")
        self.assertEqual(system_purpose.match_field("foo BAR", ["foo Bar", "foo ar"]), "foo Bar")
