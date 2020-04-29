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
from unittest.mock import patch, call, Mock
import tempfile

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core import util
from pyanaconda.core.constants import SECRET_TYPE_NONE, SECRET_TYPE_HIDDEN, SECRET_TYPE_TEXT, \
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY, \
    DEFAULT_SUBSCRIPTION_REQUEST_TYPE

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.constants.objects import RHSM_CONFIG
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest

from pyanaconda.modules.subscription.subscription import SubscriptionService
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from pyanaconda.modules.subscription.system_purpose import get_valid_fields, _normalize_field, \
    _match_field, process_field, give_the_system_purpose, SYSPURPOSE_UTILITY_PATH
from pyanaconda.modules.subscription.installation import ConnectToInsightsTask, \
    SystemPurposeConfigurationTask, RestoreRHSMLogLevelTask, TransferSubscriptionTokensTask
from pyanaconda.modules.subscription.runtime import SetRHSMConfigurationTask

from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property, \
    PropertiesChangedCallback, patch_dbus_publish_object, check_task_creation_list, \
    check_task_creation

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

    @patch("pyanaconda.core.util.execWithRedirect")
    def set_system_pourpose_no_purpose_test(self, exec_with_redirect):
        """Test that nothing is done if system has no purpose."""
        with tempfile.TemporaryDirectory() as sysroot:
            self.assertTrue(give_the_system_purpose(sysroot=sysroot,
                                                    role="",
                                                    sla="",
                                                    usage="",
                                                    addons=[]))
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def set_system_pourpose_no_syspurpose_test(self, exec_with_redirect):
        """Test that nothing is done & False is returned if the syspurpose tool is missing."""
        with tempfile.TemporaryDirectory() as sysroot:
            self.assertFalse(give_the_system_purpose(sysroot=sysroot,
                                                     role="foo",
                                                     sla="bar",
                                                     usage="baz",
                                                     addons=["a", "b", "c"]))
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def set_system_pourpose_test(self, exec_with_redirect):
        """Test that system purpose is set if syspurpose & data are both available."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create fake syspurpose tool file
            utility_path = SYSPURPOSE_UTILITY_PATH
            directory = os.path.split(utility_path)[0]
            os.makedirs(util.join_paths(sysroot, directory))
            os.mknod(util.join_paths(sysroot, utility_path))
            # set return value to 0
            exec_with_redirect.return_value = 0
            # set system purpose
            self.assertTrue(give_the_system_purpose(sysroot=sysroot,
                                                    role="foo",
                                                    sla="bar",
                                                    usage="baz",
                                                    addons=["a", "b", "c"]))
            # check syspurpose invocations look correct
            exec_with_redirect.assert_has_calls(
                [call("syspurpose", ["set-role", "foo"], root=sysroot),
                 call("syspurpose", ["set-sla", "bar"], root=sysroot),
                 call("syspurpose", ["set-usage", "baz"], root=sysroot),
                 call("syspurpose", ["add", "addons", "a", "b", "c"], root=sysroot)])

    @patch("pyanaconda.core.util.execWithRedirect")
    def set_system_pourpose_failure_test(self, exec_with_redirect):
        """Test that failure to invoke the syspurpose tool is handled correctly."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create fake syspurpose tool file
            utility_path = SYSPURPOSE_UTILITY_PATH
            directory = os.path.split(utility_path)[0]
            os.makedirs(util.join_paths(sysroot, directory))
            os.mknod(util.join_paths(sysroot, utility_path))
            # set return value no non-zero
            exec_with_redirect.return_value = 1
            # set system purpose
            self.assertFalse(give_the_system_purpose(sysroot=sysroot,
                                                     role="foo",
                                                     sla="bar",
                                                     usage="baz",
                                                     addons=["a", "b", "c"]))
            # check syspurpose invocations look correct
            exec_with_redirect.assert_called_once_with("syspurpose",
                                                       ["set-role", "foo"],
                                                       root=sysroot)


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

    def system_purpose_data_helper_test(self):
        """Test the SystemPurposeData DBus structure data availability helper method."""

        # empty
        data = SystemPurposeData()
        self.assertFalse(data.check_data_available())

        # full
        data = SystemPurposeData()
        data.role = "foo"
        data.sla = "bar"
        data.usage = "baz"
        data.addons = ["a", "b", "c"]
        self.assertTrue(data.check_data_available())

        # partially populated
        data = SystemPurposeData()
        data.role = "foo"
        data.usage = "baz"
        data.addons = ["a"]
        self.assertTrue(data.check_data_available())

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

    def subscription_attached_property_test(self):
        """Test the IsSubscriptionAttached property."""
        # should be false by default
        self.assertFalse(self.subscription_interface.IsSubscriptionAttached)

        # this property can't be set by client as it is set as the result of
        # subscription attempts, so we need to call the internal module interface
        # via a custom setter

        def custom_setter(value):
            self.subscription_module.set_subscription_attached(value)

        # check the property is True and the signal was emitted
        # - we use fake setter as there is no public setter
        self._check_dbus_property(
          "IsSubscriptionAttached",
          True,
          setter=custom_setter
        )

        # at the end the property should be True
        self.assertTrue(self.subscription_interface.IsSubscriptionAttached)

    def system_purpose_applied_property_test(self):
        """Test the IsSystemPurposeApplied property."""
        # should be false by default
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)

        # this property can't be set by client as it is set as the result of
        # system purpose to be applied, so we need to call the internal module interface
        # via a custom setter

        def custom_setter(value):
            self.subscription_module.set_is_system_purpose_applied(True)

        # check the property is True and the signal was emitted
        # - we use fake setter as there is no public setter
        self._check_dbus_property(
          "IsSystemPurposeApplied",
          True,
          setter=custom_setter
        )

        # at the end the property should be True
        self.assertTrue(self.subscription_interface.IsSystemPurposeApplied)

    @patch_dbus_publish_object
    def set_system_purpose_with_task_test(self, publisher):
        """Test SystemPurposeConfigurationTask creation."""
        # set some system purpose data
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]
        self.subscription_interface.SetSystemPurposeData(
            SystemPurposeData.to_structure(system_purpose_data)
        )
        # check the task is created correctly
        task_path = self.subscription_interface.SetSystemPurposeWithTask()
        obj = check_task_creation(self, task_path, publisher, SystemPurposeConfigurationTask)
        # check the system purpose data got propagated to the module correctly
        data_from_module = obj.implementation._system_purpose_data
        expected_dict = {
            "role": get_variant(Str, "foo"),
            "sla": get_variant(Str, "bar"),
            "usage": get_variant(Str, "baz"),
            "addons": get_variant(List[Str], ["a", "b", "c"])
        }
        self.assertEqual(SystemPurposeData.to_structure(data_from_module), expected_dict)

    @patch("pyanaconda.modules.common.task.task.Task.get_result")
    @patch("pyanaconda.modules.common.task.task.Task.run")
    @patch_dbus_publish_object
    def set_system_purpose_with_task_applied_test(self, publisher, mock_run, get_result):
        """Test system purpose is applied after SystemPurposeConfigurationTask runs."""
        # simulate successful task run
        get_result.return_value = True
        # should be false before the task runs
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)
        # run the partially mocked task
        task = self.subscription_module.set_system_purpose_with_task()
        task.run()
        # simulate the task run finishing by triggering the emitted signal manually
        task.succeeded_signal.emit()
        # check system purpose is marked as applied
        self.assertTrue(self.subscription_interface.IsSystemPurposeApplied)

    @patch("pyanaconda.modules.common.task.task.Task.get_result")
    @patch("pyanaconda.modules.common.task.task.Task.run")
    @patch_dbus_publish_object
    def set_system_purpose_with_task_applied_failure_test(self, publisher, mock_run, get_result):
        """Test system purpose is not applied after SystemPurposeConfigurationTask fails."""
        # simulate task failure
        get_result.return_value = False
        # should be false before the task runs
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)
        # run the partially mocked task
        task = self.subscription_module.set_system_purpose_with_task()
        task.run()
        # simulate the task run finishing by triggering the emitted signal manually
        task.succeeded_signal.emit()
        # check system purpose is not marked as applied due to the failure
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)

    @patch("pyanaconda.modules.subscription.installation.SystemPurposeConfigurationTask")
    def test_apply_syspurpose(self, task):
        """Test applying of system purpose on the installation environment."""
        # The _apply_syspurpose() method is used the apply system purpose data immediately
        # on the installation environment and is invoked:
        # - if system purpose data is found in kickstart
        # - before installation if system purpose data has been input by the user
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)
        self.subscription_module._apply_syspurpose()
        self.assertTrue(self.subscription_interface.IsSystemPurposeApplied)

    def get_rhsm_config_defaults_test(self):
        """Test the get_rhsm_config_defaults() method."""
        # cache should be None by default
        self.assertIsNone(self.subscription_module._rhsm_config_defaults)

        # create a default config
        default_config = {
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_HOSTNAME: "server.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_HOSTNAME: "proxy.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PORT: "1000",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_USER: "foo_user",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PASSWORD: "foo_password",
            SetRHSMConfigurationTask.CONFIG_KEY_RHSM_BASEURL: "cdn.example.com",
            "key_anaconda_does_not_use_1": "foo1",
            "key_anaconda_does_not_use_2": "foo2"
        }
        # turn it to variant, which is what RHSM DBus API will return
        default_variant = get_variant(Dict[Str, Str], default_config)

        # mock the rhsm config proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        config_proxy.GetAll.return_value = default_variant

        observer.get_proxy.return_value = config_proxy

        # query the property multiple times
        result1 = self.subscription_module.get_rhsm_config_defaults()
        result2 = self.subscription_module.get_rhsm_config_defaults()

        # make sure the results are identical
        self.assertEqual(result1, result2)

        # make sure the results contain the expected dict
        # - even though GetAll() returns a variant, the
        #   get_rhsm_config_default() should convert it
        #   to a native Python dict
        self.assertEqual(result1, default_config)
        self.assertEqual(result2, default_config)

        # check the property requested the correct DBus object
        observer.get_proxy.assert_called_once_with(RHSM_CONFIG)

        # check the mock proxy was called only once
        config_proxy.GetAll.assert_called_once_with("")

    @patch_dbus_publish_object
    def set_rhsm_config_with_task_test(self, publisher):
        """Test SetRHSMConfigurationTask creation."""
        # prepare the module with dummy data
        default_config = {
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_HOSTNAME: "server.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_HOSTNAME: "proxy.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PORT: "1000",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_USER: "foo_user",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PASSWORD: "foo_password",
            SetRHSMConfigurationTask.CONFIG_KEY_RHSM_BASEURL: "cdn.example.com",
            "key_anaconda_does_not_use_1": "foo1",
            "key_anaconda_does_not_use_2": "foo2"
        }

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

        self.subscription_interface.SetSubscriptionRequest(
            SubscriptionRequest.to_structure(full_request)
        )
        # make sure the task gets dummy rhsm config proxy that returns
        # our dummy RHSM config defaults
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        config_proxy.GetAll.return_value = default_config
        observer.get_proxy.return_value = config_proxy

        # check the task is created correctly
        task_path = self.subscription_interface.SetRHSMConfigWithTask()
        obj = check_task_creation(self, task_path, publisher, SetRHSMConfigurationTask)
        # check all the data got propagated to the module correctly
        self.assertEqual(obj.implementation._rhsm_config_proxy, config_proxy)
        task_request = obj.implementation._request
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
        self.assertEqual(
                get_native(SubscriptionRequest.to_structure(task_request)),
                expected_full_dict)
        self.assertEqual(obj.implementation._rhsm_config_defaults, default_config)

    @patch_dbus_publish_object
    def install_with_tasks_default_test(self, publisher):
        """Test install tasks - Subscription module in default state."""
        # mock the rhsm config proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        observer.get_proxy.return_value = config_proxy

        task_classes = [
            RestoreRHSMLogLevelTask,
            TransferSubscriptionTokensTask,
            ConnectToInsightsTask
        ]
        task_paths = self.subscription_interface.InstallWithTasks()
        task_objs = check_task_creation_list(self, task_paths, publisher, task_classes)

        # RestoreRHSMLogLevelTask
        obj = task_objs[0]
        self.assertEqual(obj.implementation._rhsm_config_proxy, config_proxy)

        # TransferSubscriptionTokensTask
        obj = task_objs[1]
        self.assertEqual(obj.implementation._transfer_subscription_tokens, False)

        # ConnectToInsightsTask
        obj = task_objs[2]
        self.assertEqual(obj.implementation._subscription_attached, False)
        self.assertEqual(obj.implementation._connect_to_insights, False)

    @patch_dbus_publish_object
    def install_with_tasks_configured_test(self, publisher):
        """Test install tasks - Subscription module in configured state."""

        self.subscription_interface.SetInsightsEnabled(True)
        self.subscription_module.set_subscription_attached(True)

        # mock the rhsm config proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        observer.get_proxy.return_value = config_proxy

        task_classes = [
            RestoreRHSMLogLevelTask,
            TransferSubscriptionTokensTask,
            ConnectToInsightsTask
        ]
        task_paths = self.subscription_interface.InstallWithTasks()
        task_objs = check_task_creation_list(self, task_paths, publisher, task_classes)

        # RestoreRHSMLogLevelTask
        obj = task_objs[0]
        self.assertEqual(obj.implementation._rhsm_config_proxy, config_proxy)

        # TransferSubscriptionTokensTask
        obj = task_objs[1]
        self.assertEqual(obj.implementation._transfer_subscription_tokens, True)

        # ConnectToInsightsTask
        obj = task_objs[2]
        self.assertEqual(obj.implementation._subscription_attached, True)
        self.assertEqual(obj.implementation._connect_to_insights, True)

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

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def ks_apply_syspurpose_test(self, mock_give_purpose):
        """Check that if syspurpose command is used system purpose data is applied."""
        ks_in = '''
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        self._test_kickstart(ks_in, ks_out)
        # the SystemPurposeConfigurationTask should have been called,
        # which calls give_the_system_purpose()
        mock_give_purpose.assert_called_once_with(role="FOO",
                                                  sla="BAR",
                                                  usage="BAZ",
                                                  addons=['F Product', 'B Feature'],
                                                  sysroot="/")
        # also system purpose should be marked as applied
        self.assertTrue(self.subscription_interface.IsSystemPurposeApplied)

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def ks_no_apply_syspurpose_test(self, mock_give_purpose):
        """Check that if syspurpose command is not used system purpose data is not applied."""
        ks_in = '''
        rhsm --organization="123" --activation-key="foo_key" --connect-to-insights
        '''
        ks_out = '''
        '''
        self._test_kickstart(ks_in, ks_out)
        # the SystemPurposeConfigurationTask should have been called,
        # which calls give_the_system_purpose()
        mock_give_purpose.assert_not_called()
        # also system purpose should be marked as applied
        self.assertFalse(self.subscription_interface.IsSystemPurposeApplied)
