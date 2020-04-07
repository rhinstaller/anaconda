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

from pyanaconda.core.constants import SECRET_TYPE_NONE, SECRET_TYPE_HIDDEN, SECRET_TYPE_TEXT, \
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY, \
    DEFAULT_SUBSCRIPTION_REQUEST_TYPE

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest

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

        # some of the diffs might be long if a test fails, but we still
        # want to see them
        self.maxDiff = None

    def _check_dbus_property(self, *args, **kwargs):
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

        # feed it to the DBus interface
        self.subscription_interface.SetSystemPurposeData(
            SystemPurposeData.to_structure(system_purpose_data)
        )

        # compare the result with expected data
        output = self.subscription_interface.SystemPurposeData
        self.assertEqual(output, expected_dict)

    def set_system_purpose_test(self):
        """Test if setting system purpose data from DBUS works correctly."""
        system_purpose_data = {
            "role": get_variant(Str, "foo"),
            "sla": get_variant(Str, "bar"),
            "usage": get_variant(Str, "baz"),
            "addons": get_variant(List[Str], ["a", "b", "c"])
        }

        self._check_dbus_property(
          "SystemPurposeData",
          system_purpose_data
        )

        output_structure = self.subscription_interface.SystemPurposeData
        output_system_purpose_data = SystemPurposeData.from_structure(output_structure)

        self.assertEqual(output_system_purpose_data.role, "foo")
        self.assertEqual(output_system_purpose_data.sla, "bar")
        self.assertEqual(output_system_purpose_data.usage, "baz")
        self.assertEqual(output_system_purpose_data.addons, ["a", "b", "c"])

    def subscription_request_data_defaults_test(self):
        """Test the SubscriptionRequest DBus structure defaults."""

        # create empty SubscriptionRequest structure
        empty_request = SubscriptionRequest()

        # compare with expected default values
        expected_default_dict = {
            "type": DEFAULT_SUBSCRIPTION_REQUEST_TYPE,
            "organization": "",
            "account-username": "",
            "server-hostname": "",
            "rhsm-baseurl": "",
            "server-proxy-hostname": "",
            "server-proxy-port": -1,
            "server-proxy-user": "",
            "account-password": {"type": SECRET_TYPE_NONE, "value": ""},
            "activation-keys": {"type": SECRET_TYPE_NONE, "value": []},
            "server-proxy-password": {"type": SECRET_TYPE_NONE, "value": ""},
        }

        # compare the empty structure with expected default values
        self.assertEqual(
            get_native(SubscriptionRequest.to_structure(empty_request)),
            expected_default_dict
        )

    def subscription_request_data_full_test(self):
        """Test completely populated SubscriptionRequest DBus structure."""

        # create fully populated SubscriptionRequest structure
        full_request = SubscriptionRequest()
        full_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        full_request.organization = "123456789"
        full_request.account_username = "foo_user"
        full_request.server_hostname = "candlepin.foo.com"
        full_request.rhsm_baseurl = "cdn.foo.com"
        full_request.server_proxy_hostname = "proxy.foo.com"
        full_request.server_proxy_port = 9001
        full_request.server_proxy_user = "foo_proxy_user"
        full_request.account_password.set_secret("foo_password")
        full_request.activation_keys.set_secret(["key1", "key2", "key3"])
        full_request.server_proxy_password.set_secret("foo_proxy_password")

        expected_full_dict = {
            "type": SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
            "organization": "123456789",
            "account-username": "foo_user",
            "server-hostname": "candlepin.foo.com",
            "rhsm-baseurl": "cdn.foo.com",
            "server-proxy-hostname": "proxy.foo.com",
            "server-proxy-port": 9001,
            "server-proxy-user": "foo_proxy_user",
            "account-password": {"type": SECRET_TYPE_TEXT, "value": "foo_password"},
            "activation-keys": {"type": SECRET_TYPE_TEXT, "value": ["key1", "key2", "key3"]},
            "server-proxy-password": {"type": SECRET_TYPE_TEXT, "value": "foo_proxy_password"},
        }

        # compare the fully populated structure with expected values
        self.assertEqual(
            get_native(SubscriptionRequest.to_structure(full_request)),
            expected_full_dict
        )

        # set it to the module interface
        self.subscription_interface.SetSubscriptionRequest(
            SubscriptionRequest.to_structure(full_request)
        )

        # compare the output with expected values
        output = self.subscription_interface.SubscriptionRequest
        output_dict = get_native(output)

        expected_full_output_dict = {
            "type": SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
            "organization": "123456789",
            "account-username": "foo_user",
            "server-hostname": "candlepin.foo.com",
            "rhsm-baseurl": "cdn.foo.com",
            "server-proxy-hostname": "proxy.foo.com",
            "server-proxy-port": 9001,
            "server-proxy-user": "foo_proxy_user",
            "account-password": {"type": SECRET_TYPE_HIDDEN, "value": ""},
            "activation-keys": {"type": SECRET_TYPE_HIDDEN, "value": []},
            "server-proxy-password": {"type": SECRET_TYPE_HIDDEN, "value": ""},
        }

        self.assertEqual(
            output_dict,
            expected_full_output_dict
        )

    def set_subscription_request_password_test(self):
        """Test if setting username+password subscription request from DBUS works correctly."""
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "bar_password")})
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, "foo_user"),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")})
        }

        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

    def set_subscription_request_activation_key_test(self):
        """Test if setting org + key subscription request from DBUS works correctly."""
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY),
            "organization": get_variant(Str, "123456789"),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(List[Str],
                                                  ["key_foo", "key_bar", "key_baz"])}),
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY),
            "organization": get_variant(Str, "123456789"),
            "account-username": get_variant(Str, ""),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")})
        }

        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

    def set_subscription_request_proxy_test(self):
        """Test if setting HTTP proxy in subscription request from DBUS works correctly."""
        subscription_request = {
            "server-proxy-hostname": get_variant(Str, "proxy.foo.bar"),
            "server-proxy-port": get_variant(Int, 9001),
            "server-proxy-user": get_variant(Str, "foo_proxy_user"),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "foo_proxy_password")})
        }

        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, ""),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, "proxy.foo.bar"),
            "server-proxy-port": get_variant(Int, 9001),
            "server-proxy-user": get_variant(Str, "foo_proxy_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")})
        }

        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

    def set_subscription_request_custom_urls_test(self):
        """Test if setting custom URLs in subscription request from DBUS works correctly."""
        subscription_request = {
            "server-hostname": get_variant(Str, "candlepin.foo.bar"),
            "rhsm-baseurl": get_variant(Str, "cdn.foo.bar"),
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, ""),
            "server-hostname": get_variant(Str, "candlepin.foo.bar"),
            "rhsm-baseurl": get_variant(Str, "cdn.foo.bar"),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")})
        }

        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

    def set_subscription_request_sensitive_data_wipe_test(self):
        """Test if it is possible to wipe sensitive data in SubscriptionRequest."""
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "bar_password")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(List[Str],
                                                  ["key_foo", "key_bar", "key_baz"])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "foo_proxy_password")})
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, "foo_user"),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")})
        }

        # check all three sensitive values are hidden
        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

        # indicate in SubscriptionRequest that the values should be wiped,
        # be setting all three SecureData/SecureDataList structures type
        # to NONE
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")})
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, "foo_user"),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "NONE"),
                             "value": get_variant(Str, "")})
        }

        # check all three sensitive values are wiped
        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

    def set_subscription_request_sensitive_data_keep_test(self):
        """Test if sensitive data is kept in SubscriptionRequest if a blank value comes in."""
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "bar_password")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(List[Str],
                                                  ["key_foo", "key_bar", "key_baz"])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "TEXT"),
                             "value": get_variant(Str, "foo_proxy_password")})
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, "foo_user"),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")})
        }

        # check all three sensitive values are hidden
        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

        # check all three values are actually set to what we expect
        internal_request = self.subscription_module._subscription_request
        self.assertEqual(internal_request.account_password.value,
                         "bar_password")
        self.assertEqual(internal_request.activation_keys.value,
                         ["key_foo", "key_bar", "key_baz"])
        self.assertEqual(internal_request.server_proxy_password.value,
                         "foo_proxy_password")

        # set SubscriptionRequest on input with empty value
        # and type set to HIDDEN
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")})
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, "foo_user"),
            "server-hostname": get_variant(Str, ""),
            "rhsm-baseurl": get_variant(Str, ""),
            "server-proxy-hostname": get_variant(Str, ""),
            "server-proxy-port": get_variant(Int, -1),
            "server-proxy-user": get_variant(Str, ""),
            "account-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")}),
            "activation-keys":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(List[Str], [])}),
            "server-proxy-password":
                get_variant(Structure,
                            {"type": get_variant(Str, "HIDDEN"),
                             "value": get_variant(Str, "")})
        }

        # check all the sensitive values appear to be in the correct state
        self._check_dbus_property(
          "SubscriptionRequest",
          subscription_request,
          expected_subscription_request
        )

        # check all three values are actually still set to what we expect
        internal_request = self.subscription_module._subscription_request
        self.assertEqual(internal_request.account_password.value,
                         "bar_password")
        self.assertEqual(internal_request.activation_keys.value,
                         ["key_foo", "key_bar", "key_baz"])
        self.assertEqual(internal_request.server_proxy_password.value,
                         "foo_proxy_password")

    def insights_property_test(self):
        """Test the InsightsEnabled property."""
        # should be False by default
        self.assertFalse(self.subscription_interface.InsightsEnabled)

        # try setting the property
        self._check_dbus_property(
          "InsightsEnabled",
          True
        )
        self._check_dbus_property(
          "InsightsEnabled",
          False
        )

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

    def ks_out_rhsm_parse_test(self):
        """Check the rhsm kickstart command is parsed correctly."""
        # triple quoting will not help here as the single rhsm command line
        # is longer than 100 characters & will not make our PEP8 checker happy
        ks_in = 'rhsm --organization="123" --activation-key="foo_key" --connect-to-insights ' \
                '--server-hostname="candlepin.foo.com" --rhsm-baseurl="cdn.foo.com" ' \
                '--proxy=user:pass@proxy.com:9001'

        # rhsm command is never output as we don't write out activation keys &
        # the command thus would be incomplete, resulting in an invalid kickstart
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        structure = self.subscription_interface.SubscriptionRequest
        subscription_request = SubscriptionRequest.from_structure(structure)
        # both org id and one key have been used, request should be org & key type
        self.assertEqual(subscription_request.type, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY)
        self.assertEqual(subscription_request.organization, "123")
        self.assertEqual(subscription_request.activation_keys.value, [])
        # keys should be hidden
        self.assertEqual(subscription_request.activation_keys.type,
                         SECRET_TYPE_HIDDEN)
        # account username & password should be empty
        self.assertEqual(subscription_request.account_username, "")
        self.assertEqual(subscription_request.account_password.value, "")
        self.assertEqual(subscription_request.account_password.type,
                         SECRET_TYPE_NONE)
        self.assertEqual(subscription_request.server_hostname, "candlepin.foo.com")
        self.assertEqual(subscription_request.rhsm_baseurl, "cdn.foo.com")
        self.assertEqual(subscription_request.server_proxy_hostname, "proxy.com")
        self.assertEqual(subscription_request.server_proxy_port, 9001)
        self.assertEqual(subscription_request._server_proxy_user, "user")
        self.assertEqual(subscription_request._server_proxy_password.value, "")
        self.assertEqual(subscription_request._server_proxy_password.type,
                         SECRET_TYPE_HIDDEN)

        # insights should be enabled
        self.assertTrue(self.subscription_interface.InsightsEnabled)

    def ks_out_rhsm_no_insights_test(self):
        """Check Insights is not enabled from kickstart without --connect-to-insights."""
        ks_in = '''
        rhsm --organization="123" --activation-key="foo_key"
        '''
        # rhsm command is never output as we don't write out activation keys &
        # the command thus would be incomplete resulting in an invalid kickstart
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        # insights should not be
        self.assertFalse(self.subscription_interface.InsightsEnabled)

    def ks_out_rhsm_and_syspurpose_test(self):
        """Check that if both rhsm and syspurpose are used all works correctly."""
        ks_in = '''
        rhsm --organization="123" --activation-key="foo_key" --connect-to-insights
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        # rhsm command is never output as we don't write out activation keys &
        # the command thus would be incomplete, resulting in an invalid kickstart
        ks_out = '''
        # Intended system purpose
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        self._test_kickstart(ks_in, ks_out)

        # check system purpose

        structure = self.subscription_interface.SystemPurposeData
        system_purpose_data = SystemPurposeData.from_structure(structure)
        self.assertEqual(system_purpose_data.role, 'FOO')
        self.assertEqual(system_purpose_data.sla, 'BAR')
        self.assertEqual(system_purpose_data.usage, 'BAZ')
        self.assertEqual(system_purpose_data.addons, ["F Product", "B Feature"])

        # check subscription request and insights

        structure = self.subscription_interface.SubscriptionRequest
        subscription_request = SubscriptionRequest.from_structure(structure)
        # both org id and one key have been used, request should be org & key type
        self.assertEqual(subscription_request.type, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY)
        self.assertEqual(subscription_request.organization, "123")
        self.assertEqual(subscription_request.activation_keys.value, [])
        self.assertEqual(subscription_request.activation_keys.type, SECRET_TYPE_HIDDEN)
        # insights should be enabled
        self.assertTrue(self.subscription_interface.InsightsEnabled)
