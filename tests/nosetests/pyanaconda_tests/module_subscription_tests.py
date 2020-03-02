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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import os
import unittest
import tempfile

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.structures.subscription import SystemPurposeData
from pyanaconda.modules.subscription.subscription import SubscriptionService
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.system_purpose import get_valid_fields, _normalize_field, \
    _match_field, process_field
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property, \
    PropertiesChangedCallback

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

    def system_purpose_valid_json_parsing_test(self):
        """Test that the JSON file holding valid system purpose values is parsed correctly."""
        # check file missing completely
        # - use path in tempdir to a file that has not been created and thus does not exist
        with tempfile.TemporaryDirectory() as tempdir:
            no_file = os.path.join(tempdir, "foo.json")
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=no_file)
            self.assertListEqual(roles, [])
            self.assertListEqual(slas, [])
            self.assertListEqual(usage_types, [])

        # check empty value list is handled correctly
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:
            testfile.write(SYSPURPOSE_VALID_VALUES_JSON_EMPTY)
            testfile.flush()
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=testfile.name)
            self.assertListEqual(roles, [])
            self.assertListEqual(slas, [])
            self.assertListEqual(usage_types, [])

        # check correctly populated json file is parsed correctly
        with tempfile.NamedTemporaryFile(mode="w+t") as testfile:
            testfile.write(SYSPURPOSE_VALID_VALUES_JSON)
            testfile.flush()
            roles, slas, usage_types = get_valid_fields(valid_fields_file_path=testfile.name)
            self.assertListEqual(roles, ["role_a", "role_b", "role_c"])
            self.assertListEqual(slas, ["sla_a", "sla_b", "sla_c"])
            self.assertListEqual(usage_types, ["usage_a", "usage_b", "usage_c"])

    def normalize_field_test(self):
        """Test that the system purpose valid field normalization works."""
        # this should basically just lower case the input
        self.assertEqual(_normalize_field("AAA"), "aaa")
        self.assertEqual(_normalize_field("Ab"), "ab")
        self.assertEqual(_normalize_field("A b C"), "a b c")

    def match_field_test(self):
        """Test that the system purpose valid field matching works."""
        # The function is used on system purpose data from kickstart
        # and it tries to match the given value to a well known value
        # from the valid field.json. This way we can pre-select values
        # in the GUI even if the user typosed the case or similar.

        # these should match
        self.assertEqual(
            _match_field("production", ["Production", "Development", "Testing"]),
            "Production"
        )
        self.assertEqual(
            _match_field("Production", ["Production", "Development", "Testing"]),
            "Production"
        )
        self.assertEqual(
            _match_field("DEVELOPMENT", ["Production", "Development", "Testing"]),
            "Development"
        )

        # these should not match but return the original value
        self.assertIsNone(
            _match_field("custom", ["Production", "Development", "Testing"]),
        )
        self.assertIsNone(
            _match_field("Prod", ["Production", "Development", "Testing"]),
        )
        self.assertIsNone(
            _match_field("Production 1", ["Production", "Development", "Testing"]),
        )
        self.assertIsNone(
            _match_field("Production Development", ["Production", "Development", "Testing"]),
        )

    def process_field_test(self):
        """Test that the system purpose field processing works."""

        valid_values = ["Production", "Development", "Testing"]

        # empty string
        self.assertEqual(process_field("", valid_values, "usage"), "")

        # well known value with different case
        self.assertEqual(process_field("production", valid_values, "usage"), "Production")
        self.assertEqual(process_field("PRODUCTION", valid_values, "usage"), "Production")

        # well known value with matching case
        self.assertEqual(process_field("Production", valid_values, "usage"), "Production")

        # fully custom value
        self.assertEqual(process_field("foo", valid_values, "usage"), "foo")
        self.assertEqual(process_field("foo BAR", valid_values, "usage"), "foo BAR")

        # empty list of well known values
        self.assertEqual(process_field("PRODUCTION", [], "usage"), "PRODUCTION")
        self.assertEqual(process_field("foo", [], "usage"), "foo")


class SubscriptionInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the subscription module."""

    def setUp(self):
        """Set up the subscription module."""
        self.subscription_module = SubscriptionService()
        self.subscription_interface = SubscriptionInterface(self.subscription_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.subscription_interface.PropertiesChanged.connect(self.callback)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            SUBSCRIPTION,
            self.subscription_interface,
            *args, **kwargs
        )

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.subscription_interface.KickstartCommands, ["syspurpose", "rhsm"])
        self.assertEqual(self.subscription_interface.KickstartSections, [])
        self.assertEqual(self.subscription_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def system_purpose_data_test(self):
        """Test the SystemPurposeData DBus structure."""

        # create the SystemPurposeData structure
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]

        # create its expected representation
        expected_dict = {
            "role": get_variant(Str, "foo"),
            "sla": get_variant(Str, "bar"),
            "usage": get_variant(Str, "baz"),
            "addons": get_variant(List[Str], ["a", "b", "c"])
        }

        # compare the two
        self.assertEqual(SystemPurposeData.to_structure(system_purpose_data), expected_dict)

    def set_system_purpose_test(self):
        """Test if setting system purpose data from DBUS works correctly."""
        system_purpose_data = {
            "role": get_variant(Str, "foo"),
            "sla": get_variant(Str, "bar"),
            "usage": get_variant(Str, "baz"),
            "addons": get_variant(List[Str], ["a", "b", "c"])
        }

        self._test_dbus_property(
          "SystemPurposeData",
          system_purpose_data
        )

        output_structure = self.subscription_interface.SystemPurposeData
        output_system_purpose_data = SystemPurposeData.from_structure(output_structure)

        self.assertEqual(output_system_purpose_data.role, "foo")
        self.assertEqual(output_system_purpose_data.sla, "bar")
        self.assertEqual(output_system_purpose_data.usage, "baz")
        self.assertEqual(output_system_purpose_data.addons, ["a", "b", "c"])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.subscription_interface, ks_in, ks_out)

    def ks_out_no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def ks_out_command_only_test(self):
        """Test with only syspurpose command being used."""
        ks_in = "syspurpose"
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        # also test resulting module state
        structure = self.subscription_interface.SystemPurposeData
        system_purpose_data = SystemPurposeData.from_structure(structure)
        self.assertEqual(system_purpose_data.role, "")
        self.assertEqual(system_purpose_data.sla, "")
        self.assertEqual(system_purpose_data.usage, "")
        self.assertEqual(system_purpose_data.addons, [])

    def ks_out_set_role_test(self):
        """Check kickstart with role being used."""
        ks_in = '''
        syspurpose --role="FOO ROLE"
        '''
        ks_out = '''
        # Intended system purpose\nsyspurpose --role="FOO ROLE"
        '''
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_sla_test(self):
        """Check kickstart with SLA being used."""
        ks_in = '''
        syspurpose --sla="FOO SLA"
        '''
        ks_out = '''
        # Intended system purpose\nsyspurpose --sla="FOO SLA"
        '''
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_usage_test(self):
        """Check kickstart with usage being used."""
        ks_in = '''
        syspurpose --usage="FOO USAGE"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --usage="FOO USAGE"
        '''
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_addons_test(self):
        """Check kickstart with addons being used."""
        ks_in = '''
        syspurpose --addon="Foo Product" --addon="Bar Feature"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --addon="Foo Product" --addon="Bar Feature"
        '''
        self._test_kickstart(ks_in, ks_out)

    def ks_out_set_all_usage_test(self):
        """Check kickstart with all options being used."""
        ks_in = '''
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        self._test_kickstart(ks_in, ks_out)

        structure = self.subscription_interface.SystemPurposeData
        system_purpose_data = SystemPurposeData.from_structure(structure)
        self.assertEqual(system_purpose_data.role, 'FOO')
        self.assertEqual(system_purpose_data.sla, 'BAR')
        self.assertEqual(system_purpose_data.usage, 'BAZ')
        self.assertEqual(system_purpose_data.addons, ["F Product", "B Feature"])
