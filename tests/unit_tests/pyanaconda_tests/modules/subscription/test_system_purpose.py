#
# Copyright (C) 2021  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>

import os
import tempfile
import unittest
from unittest.mock import Mock

from dasbus.error import DBusError
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.subscription.system_purpose import (
    _match_field,
    _normalize_field,
    get_valid_fields,
    give_the_system_purpose,
    process_field,
)

# content of a valid populated valid values json file for system purpose testing
SYSPURPOSE_VALID_VALUES_JSON = """
{
"role" : ["role_a", "role_b", "role_c"],
"service_level_agreement" : ["sla_a", "sla_b", "sla_c"],
"usage" : ["usage_a", "usage_b", "usage_c"]
}
"""

# content of a valid but not populated valid values json file for system purpose testing
SYSPURPOSE_VALID_VALUES_JSON_EMPTY = """
{
"role" : [],
"service_level_agreement" : [],
"usage" : []
}
"""


class SystemPurposeLibraryTestCase(unittest.TestCase):
    """Test the system purpose data handling code."""

    def test_system_purpose_valid_json_parsing(self):
        """Test that the JSON file holding valid system purpose values is parsed correctly."""
        # check file missing completely
        # - use path in tempdir to a file that has not been created and thus does not exist
        with tempfile.TemporaryDirectory() as tempdir:
            no_file = os.path.join(tempdir, "foo.json")
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=no_file)
            assert roles == []
            assert slas == []
            assert usage_types == []

        # check empty value list is handled correctly
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:
            testfile.write(SYSPURPOSE_VALID_VALUES_JSON_EMPTY)
            testfile.flush()
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=testfile.name)
            assert roles == []
            assert slas == []
            assert usage_types == []

        # check correctly populated json file is parsed correctly
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:
            testfile.write(SYSPURPOSE_VALID_VALUES_JSON)
            testfile.flush()
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=testfile.name)
            assert roles == ["role_a", "role_b", "role_c"]
            assert slas == ["sla_a", "sla_b", "sla_c"]
            assert usage_types == ["usage_a", "usage_b", "usage_c"]

    def test_normalize_field(self):
        """Test that the system purpose valid field normalization works."""
        # this should basically just lower case the input
        assert _normalize_field("AAA") == "aaa"
        assert _normalize_field("Ab") == "ab"
        assert _normalize_field("A b C") == "a b c"

    def test_match_field(self):
        """Test that the system purpose valid field matching works."""
        # The function is used on system purpose data from kickstart
        # and it tries to match the given value to a well known value
        # from the valid field.json. This way we can pre-select values
        # in the GUI even if the user typosed the case or similar.

        # these should match
        assert _match_field("production", ["Production", "Development", "Testing"]) == \
            "Production"
        assert _match_field("Production", ["Production", "Development", "Testing"]) == \
            "Production"
        assert _match_field("DEVELOPMENT", ["Production", "Development", "Testing"]) == \
            "Development"

        # these should not match but return the original value
        assert _match_field("custom", ["Production", "Development", "Testing"]) is None
        assert _match_field("Prod", ["Production", "Development", "Testing"]) is None
        assert _match_field("Production 1", ["Production", "Development", "Testing"]) is None
        assert _match_field("Production Development",
                            ["Production", "Development", "Testing"]) is None

    def test_process_field(self):
        """Test that the system purpose field processing works."""

        valid_values = ["Production", "Development", "Testing"]

        # empty string
        assert process_field("", valid_values, "usage") == ""

        # well known value with different case
        assert process_field("production", valid_values, "usage") == "Production"
        assert process_field("PRODUCTION", valid_values, "usage") == "Production"

        # well known value with matching case
        assert process_field("Production", valid_values, "usage") == "Production"

        # fully custom value
        assert process_field("foo", valid_values, "usage") == "foo"
        assert process_field("foo BAR", valid_values, "usage") == "foo BAR"

        # empty list of well known values
        assert process_field("PRODUCTION", [], "usage") == "PRODUCTION"
        assert process_field("foo", [], "usage") == "foo"

    def test_set_system_pourpose_no_purpose(self):
        """Test that nothing is done if system has no purpose."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create fake RHSM Syspurpose DBus proxy
            syspurpose_proxy = Mock()
            assert give_the_system_purpose(sysroot=sysroot,
                                           rhsm_syspurpose_proxy=syspurpose_proxy,
                                           role="",
                                           sla="",
                                           usage="",
                                           addons=[])
            syspurpose_proxy.SetSyspurpose.assert_not_called()

    def test_set_system_pourpose(self):
        """Test that system purpose is set if syspurpose & data are both available."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create fake RHSM Syspurpose DBus proxy
            syspurpose_proxy = Mock()
            # set system purpose
            assert give_the_system_purpose(sysroot=sysroot,
                                           rhsm_syspurpose_proxy=syspurpose_proxy,
                                           role="foo",
                                           sla="bar",
                                           usage="baz",
                                           addons=["a", "b", "c"])
            # check syspurpose invocations look correct
            syspurpose_proxy.SetSyspurpose.assert_called_once_with(
                {
                    "role": get_variant(Str, "foo"),
                    "service_level_agreement": get_variant(Str, "bar"),
                    "usage": get_variant(Str, "baz"),
                    "addons": get_variant(List[Str], ["a", "b", "c"])
                },
                'en_US.UTF-8'
            )

    def test_set_system_pourpose_failure(self):
        """Test that exception raised by SetSyspurpose DBus call is handled correctly."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create fake RHSM Syspurpose DBus proxy
            syspurpose_proxy = Mock()
            # raise DBusError with error message in JSON
            syspurpose_proxy.SetSyspurpose.side_effect = DBusError("syspurpose error")
            # set system purpose & False is returned due to the exception
            assert not give_the_system_purpose(sysroot=sysroot,
                                               rhsm_syspurpose_proxy=syspurpose_proxy,
                                               role="foo",
                                               sla="bar",
                                               usage="baz",
                                               addons=["a", "b", "c"])
            # check the fake DBus method still was called correctly
            syspurpose_proxy.SetSyspurpose.assert_called_once_with(
                {
                    "role": get_variant(Str, "foo"),
                    "service_level_agreement": get_variant(Str, "bar"),
                    "usage": get_variant(Str, "baz"),
                    "addons": get_variant(List[Str], ["a", "b", "c"])
                },
                'en_US.UTF-8'
            )
