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
import unittest
from unittest.mock import Mock, patch

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import (
    DEFAULT_SUBSCRIPTION_REQUEST_TYPE,
    SECRET_TYPE_HIDDEN,
    SECRET_TYPE_NONE,
    SECRET_TYPE_TEXT,
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD,
)
from pyanaconda.modules.common.constants.objects import RHSM_CONFIG
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.structures.subscription import (
    AttachedSubscription,
    SubscriptionRequest,
    SystemPurposeData,
)
from pyanaconda.modules.subscription.installation import (
    ConnectToInsightsTask,
    ProvisionTargetSystemForSatelliteTask,
    RestoreRHSMDefaultsTask,
    TransferSubscriptionTokensTask,
)
from pyanaconda.modules.subscription.runtime import (
    RegisterAndSubscribeTask,
    RetrieveOrganizationsTask,
    SetRHSMConfigurationTask,
    SystemPurposeConfigurationTask,
    UnregisterTask,
)
from pyanaconda.modules.subscription.subscription import SubscriptionService
from pyanaconda.modules.subscription.subscription_interface import SubscriptionInterface
from tests.unit_tests.pyanaconda_tests import (
    PropertiesChangedCallback,
    check_dbus_property,
    check_kickstart_interface,
    check_task_creation,
    check_task_creation_list,
    patch_dbus_publish_object,
)


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
            SUBSCRIPTION,
            self.subscription_interface,
            *args, **kwargs
        )

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.subscription_interface.KickstartCommands == ["syspurpose", "rhsm"]
        assert self.subscription_interface.KickstartSections == []
        assert self.subscription_interface.KickstartAddons == []
        self.callback.assert_not_called()

    def test_system_purpose_data(self):
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
        assert SystemPurposeData.to_structure(system_purpose_data) == expected_dict

        # feed it to the DBus interface
        self.subscription_interface.SetSystemPurposeData(
            SystemPurposeData.to_structure(system_purpose_data)
        )

        # compare the result with expected data
        output = self.subscription_interface.SystemPurposeData
        assert output == expected_dict

    def test_system_purpose_data_comparison(self):
        """Test SystemPurposeData instance equality comparison."""
        # This is important as we use the comparison to decide if newly set system purpose data
        # is different and we should set it to the system or not if it is the same.

        # create the SystemPurposeData structure
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]

        # create a clone of the structure - new instance same data
        system_purpose_data_clone = SystemPurposeData()
        system_purpose_data_clone.role = "foo"
        system_purpose_data_clone.sla = "bar"
        system_purpose_data_clone.usage = "baz"
        system_purpose_data_clone.addons = ["a", "b", "c"]

        # create the SystemPurposeData structure
        different_system_purpose_data = SystemPurposeData()
        different_system_purpose_data.role = "different_foo"
        different_system_purpose_data.sla = "different_bar"
        different_system_purpose_data.usage = "different_baz"
        different_system_purpose_data.addons = ["different_a", "different_b", "different_c"]

        # same content should be considered the same
        assert system_purpose_data == system_purpose_data_clone

        # different content should not be considered the same
        assert not (system_purpose_data == different_system_purpose_data)
        assert not (system_purpose_data_clone == different_system_purpose_data)

        # comparing with something else than a SystemPurposeData instance should
        # not crash & always return False
        assert system_purpose_data != "foo"
        assert system_purpose_data is not None
        assert system_purpose_data != object()

    def test_system_purpose_data_helper(self):
        """Test the SystemPurposeData DBus structure data availability helper method."""

        # empty
        data = SystemPurposeData()
        assert not data.check_data_available()

        # full
        data = SystemPurposeData()
        data.role = "foo"
        data.sla = "bar"
        data.usage = "baz"
        data.addons = ["a", "b", "c"]
        assert data.check_data_available()

        # partially populated
        data = SystemPurposeData()
        data.role = "foo"
        data.usage = "baz"
        data.addons = ["a"]
        assert data.check_data_available()

    def test_set_system_purpose(self):
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

        assert output_system_purpose_data.role == "foo"
        assert output_system_purpose_data.sla == "bar"
        assert output_system_purpose_data.usage == "baz"
        assert output_system_purpose_data.addons == ["a", "b", "c"]

    def test_subscription_request_data_defaults(self):
        """Test the SubscriptionRequest DBus structure defaults."""

        # create empty SubscriptionRequest structure
        empty_request = SubscriptionRequest()

        # compare with expected default values
        expected_default_dict = {
            "type": DEFAULT_SUBSCRIPTION_REQUEST_TYPE,
            "organization": "",
            "account-username": "",
            "account-organization": "",
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
        assert get_native(SubscriptionRequest.to_structure(empty_request)) == \
            expected_default_dict

    def test_subscription_request_data_full(self):
        """Test completely populated SubscriptionRequest DBus structure."""

        # create fully populated SubscriptionRequest structure
        full_request = SubscriptionRequest()
        full_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        full_request.organization = "123456789"
        full_request.account_username = "foo_user"
        full_request.account_organization = "foo_account_org"
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
            "account-organization": "foo_account_org",
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
        assert get_native(SubscriptionRequest.to_structure(full_request)) == \
            expected_full_dict

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
            "account-organization": "foo_account_org",
            "server-hostname": "candlepin.foo.com",
            "rhsm-baseurl": "cdn.foo.com",
            "server-proxy-hostname": "proxy.foo.com",
            "server-proxy-port": 9001,
            "server-proxy-user": "foo_proxy_user",
            "account-password": {"type": SECRET_TYPE_HIDDEN, "value": ""},
            "activation-keys": {"type": SECRET_TYPE_HIDDEN, "value": []},
            "server-proxy-password": {"type": SECRET_TYPE_HIDDEN, "value": ""},
        }

        assert output_dict == \
            expected_full_output_dict

    def test_set_subscription_request_password(self):
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
            "account-organization": get_variant(Str, ""),
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

    def test_set_subscription_request_activation_key(self):
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
            "account-organization": get_variant(Str, ""),
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

    def test_set_subscription_request_proxy(self):
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
            "account-organization": get_variant(Str, ""),
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

    def test_set_subscription_request_custom_urls(self):
        """Test if setting custom URLs in subscription request from DBUS works correctly."""
        subscription_request = {
            "server-hostname": get_variant(Str, "candlepin.foo.bar"),
            "rhsm-baseurl": get_variant(Str, "cdn.foo.bar"),
        }
        expected_subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "organization": get_variant(Str, ""),
            "account-username": get_variant(Str, ""),
            "account-organization": get_variant(Str, ""),
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

    def test_set_subscription_request_sensitive_data_wipe(self):
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
            "account-organization": get_variant(Str, ""),
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
            "account-organization": get_variant(Str, ""),
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

    def test_set_subscription_request_sensitive_data_keep(self):
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
            "account-organization": get_variant(Str, ""),
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
        assert internal_request.account_password.value == \
            "bar_password"
        assert internal_request.activation_keys.value == \
            ["key_foo", "key_bar", "key_baz"]
        assert internal_request.server_proxy_password.value == \
            "foo_proxy_password"

        # set SubscriptionRequest on input with empty value
        # and type set to HIDDEN
        subscription_request = {
            "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
            "account-username": get_variant(Str, "foo_user"),
            "account-organization": get_variant(Str, ""),
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
            "account-organization": get_variant(Str, ""),
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
        assert internal_request.account_password.value == \
            "bar_password"
        assert internal_request.activation_keys.value == \
            ["key_foo", "key_bar", "key_baz"]
        assert internal_request.server_proxy_password.value == \
            "foo_proxy_password"

    def test_attached_subscription_defaults(self):
        """Test the AttachedSubscription DBus structure defaults."""

        # create empty AttachedSubscription structure
        empty_request = AttachedSubscription()

        # compare with expected default values
        expected_default_dict = {
            "name": get_variant(Str, ""),
            "service-level": get_variant(Str, ""),
            "sku": get_variant(Str, ""),
            "contract": get_variant(Str, ""),
            "start-date": get_variant(Str, ""),
            "end-date": get_variant(Str, ""),
            "consumed-entitlement-count": get_variant(Int, 1)
        }
        # compare the empty structure with expected default values
        assert AttachedSubscription.to_structure(empty_request) == \
            expected_default_dict

    def test_attached_subscription_full(self):
        """Test the AttachedSubscription DBus structure that is fully populated."""

        # create empty AttachedSubscription structure
        full_request = AttachedSubscription()
        full_request.name = "Foo Bar Beta"
        full_request.service_level = "really good"
        full_request.sku = "ABCD1234"
        full_request.contract = "87654321"
        full_request.start_date = "Jan 01, 1970"
        full_request.end_date = "Jan 19, 2038"
        full_request.consumed_entitlement_count = 9001

        # compare with expected values
        expected_default_dict = {
            "name": get_variant(Str, "Foo Bar Beta"),
            "service-level": get_variant(Str, "really good"),
            "sku": get_variant(Str, "ABCD1234"),
            "contract": get_variant(Str, "87654321"),
            "start-date": get_variant(Str, "Jan 01, 1970"),
            "end-date": get_variant(Str, "Jan 19, 2038"),
            "consumed-entitlement-count": get_variant(Int, 9001)
        }
        # compare the full structure with expected values
        assert AttachedSubscription.to_structure(full_request) == \
            expected_default_dict

    def test_insights_property(self):
        """Test the InsightsEnabled property."""
        # should be False by default
        assert not self.subscription_interface.InsightsEnabled

        # try setting the property
        self._check_dbus_property(
          "InsightsEnabled",
          True
        )
        self._check_dbus_property(
          "InsightsEnabled",
          False
        )

    def test_registered_property(self):
        """Test the IsRegistered property."""
        # should be false by default
        assert not self.subscription_interface.IsRegistered

        # this property can't be set by client as it is set as the result of
        # subscription attempts, so we need to call the internal module interface
        # via a custom setter

        def custom_setter(value):
            self.subscription_module.set_registered(value)

        # check the property is True and the signal was emitted
        # - we use fake setter as there is no public setter
        self._check_dbus_property(
          "IsRegistered",
          True,
          setter=custom_setter
        )

        # at the end the property should be True
        assert self.subscription_interface.IsRegistered

    def test_simple_content_access_property(self):
        """Test the IsSimpleContentAccessEnabled property."""
        # should be false by default
        assert not self.subscription_interface.IsSimpleContentAccessEnabled

        # this property can't be set by client as it is set as the result of
        # subscription attempts, so we need to call the internal module interface
        # via a custom setter

        def custom_setter(value):
            self.subscription_module.set_simple_content_access_enabled(value)

        # check the property is True and the signal was emitted
        # - we use fake setter as there is no public setter
        self._check_dbus_property(
          "IsSimpleContentAccessEnabled",
          True,
          setter=custom_setter
        )

        # at the end the property should be True
        assert self.subscription_interface.IsSimpleContentAccessEnabled

    def test_subscription_attached_property(self):
        """Test the IsSubscriptionAttached property."""
        # should be false by default
        assert not self.subscription_interface.IsSubscriptionAttached

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
        assert self.subscription_interface.IsSubscriptionAttached

    def test_attached_subscriptions_property(self):
        """Test the AttachedSubscriptions property."""
        # should return an empty list by default
        assert self.subscription_interface.AttachedSubscriptions == []
        # this property can't be set by client as it is set as the result of
        # subscription attempts, so we need to call the internal module interface
        # via a custom setter

        def custom_setter(struct_list):
            instance_list = AttachedSubscription.from_structure_list(struct_list)
            self.subscription_module.set_attached_subscriptions(instance_list)

        # prepare some testing data
        subscription_structs = [
            {
                "name": get_variant(Str, "Foo Bar Beta"),
                "service-level": get_variant(Str, "very good"),
                "sku": get_variant(Str, "ABC1234"),
                "contract": get_variant(Str, "12345678"),
                "start-date": get_variant(Str, "May 12, 2020"),
                "end-date": get_variant(Str, "May 12, 2021"),
                "consumed-entitlement-count": get_variant(Int, 1)
            },
            {
                "name": get_variant(Str, "Foo Bar Beta NG"),
                "service-level": get_variant(Str, "even better"),
                "sku": get_variant(Str, "ABC4321"),
                "contract": get_variant(Str, "87654321"),
                "start-date": get_variant(Str, "now"),
                "end-date": get_variant(Str, "never"),
                "consumed-entitlement-count": get_variant(Int, 1000)
            }
        ]
        # check the property is True and the signal was emitted
        # - we use fake setter as there is no public setter
        self._check_dbus_property(
          "AttachedSubscriptions",
          subscription_structs,
          setter=custom_setter
        )
        # at the end the property should return the expected list
        # of AttachedSubscription structures
        assert self.subscription_interface.AttachedSubscriptions == subscription_structs

    @patch_dbus_publish_object
    def test_set_system_purpose_with_task(self, publisher):
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
        # mock the rhsm syspurpose proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        syspurpose_proxy = Mock()
        observer.get_proxy.return_value = syspurpose_proxy
        # check the task is created correctly
        task_path = self.subscription_interface.SetSystemPurposeWithTask()
        obj = check_task_creation(task_path, publisher, SystemPurposeConfigurationTask)
        # check the system purpose data got propagated to the module correctly
        data_from_module = obj.implementation._system_purpose_data
        expected_dict = {
            "role": get_variant(Str, "foo"),
            "sla": get_variant(Str, "bar"),
            "usage": get_variant(Str, "baz"),
            "addons": get_variant(List[Str], ["a", "b", "c"])
        }
        assert SystemPurposeData.to_structure(data_from_module) == expected_dict

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def test_apply_syspurpose(self, mock_give_purpose):
        """Test applying of system purpose on the installation environment."""
        # The _apply_syspurpose() method is used the apply system purpose data immediately
        # on the installation environment.
        # create some system purpose data
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]
        # feed it to the DBus interface
        self.subscription_interface.SetSystemPurposeData(
            SystemPurposeData.to_structure(system_purpose_data)
        )
        # mock the rhsm syspurpose proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        syspurpose_proxy = Mock()
        observer.get_proxy.return_value = syspurpose_proxy
        # call the method we are testing
        self.subscription_module._apply_syspurpose()
        mock_give_purpose.assert_called_once_with(
            sysroot="/",
            rhsm_syspurpose_proxy=syspurpose_proxy,
            role="foo",
            sla="bar",
            usage="baz",
            addons=["a", "b", "c"]
        )

    def test_get_rhsm_config_defaults(self):
        """Test the get_rhsm_config_defaults() method."""
        # cache should be None by default
        assert self.subscription_module._rhsm_config_defaults is None

        # create a default config
        default_config = {
            "server":
                {
                    "hostname": "server.example.com",
                    "proxy_hostname": "proxy.example.com",
                    "proxy_port": "1000",
                    "proxy_user": "foo_user",
                    "proxy_password": "foo_password",
                },
            "rhsm":
                {
                    "baseurl": "cdn.example.com",
                    "key_anaconda_does_not_use_1": "foo1",
                    "key_anaconda_does_not_use_2": "foo2"
                }
        }

        # create expected output - flat version of the nested default config
        flat_default_config = {
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_HOSTNAME: "server.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_HOSTNAME: "proxy.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PORT: "1000",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_USER: "foo_user",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PASSWORD: "foo_password",
            SetRHSMConfigurationTask.CONFIG_KEY_RHSM_BASEURL: "cdn.example.com",
            "rhsm.key_anaconda_does_not_use_1": "foo1",
            "rhsm.key_anaconda_does_not_use_2": "foo2"
        }

        # turn it to variant, which is what RHSM DBus API will return
        default_variant = get_variant(Dict[Str, Dict[Str, Str]], default_config)

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
        assert result1 == result2

        # make sure the results contain the expected dict
        # - even though GetAll() returns a variant, the
        #   get_rhsm_config_default() should convert it
        #   to a native Python dict
        assert result1 == flat_default_config
        assert result2 == flat_default_config

        # check the property requested the correct DBus object
        observer.get_proxy.assert_called_once_with(RHSM_CONFIG)

        # check the mock proxy was called only once
        config_proxy.GetAll.assert_called_once_with("")

    def test_package_requirements_default(self):
        """Test package requirements - module in default state."""
        # by default no packages should be required
        requirements = self.subscription_interface.CollectRequirements()
        assert requirements == []

    def test_package_requirements_insights(self):
        """Test package requirements - connect to Insights enabled."""
        # enable connect to Insights & mark system as subscribed
        self.subscription_interface.SetInsightsEnabled(True)
        self.subscription_module.set_subscription_attached(True)
        # check the Insights client package is requested
        requirements = self.subscription_interface.CollectRequirements()
        expected_requirements = [
            {"name": "insights-client",
             "reason": "Needed to connect the target system to Red Hat Insights.",
             "type": "package"}
        ]
        assert get_native(requirements) == expected_requirements

    @patch_dbus_publish_object
    def test_set_rhsm_config_with_task(self, publisher):
        """Test SetRHSMConfigurationTask creation."""
        # prepare the module with dummy data
        default_config = {
            "server":
                {
                    "hostname": "server.example.com",
                    "proxy_hostname": "proxy.example.com",
                    "proxy_port": "1000",
                    "proxy_user": "foo_user",
                    "proxy_password": "foo_password",
                },
            "rhsm":
                {
                    "baseurl": "cdn.example.com",
                    "key_anaconda_does_not_use_1": "foo1",
                    "key_anaconda_does_not_use_2": "foo2"
                }
        }

        # create expected output - flat version of the nested default config
        flat_default_config = {
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_HOSTNAME: "server.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_HOSTNAME: "proxy.example.com",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PORT: "1000",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_USER: "foo_user",
            SetRHSMConfigurationTask.CONFIG_KEY_SERVER_PROXY_PASSWORD: "foo_password",
            SetRHSMConfigurationTask.CONFIG_KEY_RHSM_BASEURL: "cdn.example.com",
            "rhsm.key_anaconda_does_not_use_1": "foo1",
            "rhsm.key_anaconda_does_not_use_2": "foo2"
        }

        full_request = SubscriptionRequest()
        full_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        full_request.organization = "123456789"
        full_request.account_username = "foo_user"
        full_request.account_organization = "foo_account_organization"
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
        obj = check_task_creation(task_path, publisher, SetRHSMConfigurationTask)
        # check all the data got propagated to the module correctly
        assert obj.implementation._rhsm_config_proxy == config_proxy
        task_request = obj.implementation._request
        expected_full_dict = {
            "type": SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
            "organization": "123456789",
            "account-username": "foo_user",
            "account-organization": "foo_account_organization",
            "server-hostname": "candlepin.foo.com",
            "rhsm-baseurl": "cdn.foo.com",
            "server-proxy-hostname": "proxy.foo.com",
            "server-proxy-port": 9001,
            "server-proxy-user": "foo_proxy_user",
            "account-password": {"type": SECRET_TYPE_TEXT, "value": "foo_password"},
            "activation-keys": {"type": SECRET_TYPE_TEXT, "value": ["key1", "key2", "key3"]},
            "server-proxy-password": {"type": SECRET_TYPE_TEXT, "value": "foo_proxy_password"},
        }
        assert get_native(SubscriptionRequest.to_structure(task_request)) == expected_full_dict
        assert obj.implementation._rhsm_config_defaults == flat_default_config

    @patch_dbus_publish_object
    def test_register_and_subscribe(self, publisher):
        """Test RegisterAndSubscribeTask creation - org + key."""
        # prepare dummy objects for the task
        rhsm_observer = Mock()
        self.subscription_module._rhsm_observer = rhsm_observer
        subscription_request = Mock()
        self.subscription_module._subscription_request = subscription_request
        system_purpose_data = Mock()
        self.subscription_module._system_purpose_data = system_purpose_data
        # check the task is created correctly
        task_path = self.subscription_interface.RegisterAndSubscribeWithTask()
        obj = check_task_creation(task_path, publisher, RegisterAndSubscribeTask)
        # check all the data got propagated to the task correctly
        assert obj.implementation._rhsm_observer == rhsm_observer
        assert obj.implementation._subscription_request == subscription_request
        assert obj.implementation._system_purpose_data == system_purpose_data
        # pylint: disable=comparison-with-callable
        assert obj.implementation._registered_callback == self.subscription_module.set_registered
        # pylint: disable=comparison-with-callable
        assert obj.implementation._registered_to_satellite_callback == \
            self.subscription_module.set_registered_to_satellite
        assert obj.implementation._simple_content_access_callback == \
            self.subscription_module.set_simple_content_access_enabled
        # pylint: disable=comparison-with-callable
        assert obj.implementation._subscription_attached_callback == \
            self.subscription_module.set_subscription_attached
        # pylint: disable=comparison-with-callable
        assert obj.implementation._subscription_data_callback == \
            self.subscription_module._set_system_subscription_data
        # pylint: disable=comparison-with-callable
        assert obj.implementation._satellite_script_downloaded_callback == \
            self.subscription_module._set_satellite_provisioning_script
        # pylint: disable=comparison-with-callable
        assert obj.implementation._config_backup_callback == \
            self.subscription_module._set_pre_satellite_rhsm_conf_snapshot
        # trigger the succeeded signal
        obj.implementation.succeeded_signal.emit()

    @patch_dbus_publish_object
    def test_unregister(self, publisher):
        """Test UnregisterTask creation."""
        # simulate system being subscribed
        self.subscription_module.set_subscription_attached(True)
        # make sure the task gets dummy rhsm observer
        rhsm_observer = Mock()
        self.subscription_module._rhsm_observer = rhsm_observer
        # check the task is created correctly
        task_path = self.subscription_interface.UnregisterWithTask()
        obj = check_task_creation(task_path, publisher, UnregisterTask)
        # check all the data got propagated to the module correctly
        assert obj.implementation._rhsm_observer == rhsm_observer
        assert obj.implementation._registered_to_satellite is False
        assert obj.implementation._rhsm_configuration == {}
        # trigger the succeeded signal
        obj.implementation.succeeded_signal.emit()
        # check unregistration set the subscription-attached, registered
        # and SCA properties to False
        assert self.subscription_interface.IsRegistered is False
        assert self.subscription_interface.IsRegisteredToSatellite is False
        assert self.subscription_interface.IsSimpleContentAccessEnabled is False
        assert self.subscription_interface.IsSubscriptionAttached is False

    @patch_dbus_publish_object
    def test_unregister_satellite(self, publisher):
        """Test UnregisterTask creation - system registered to Satellite."""
        # simulate system being subscribed & registered to Satellite
        self.subscription_module.set_subscription_attached(True)
        self.subscription_module._set_satellite_provisioning_script("foo script")
        self.subscription_module.set_registered_to_satellite(True)
        # lets also set SCA as enabled
        self.subscription_module.set_simple_content_access_enabled(True)
        # simulate RHSM config backup
        self.subscription_module._rhsm_conf_before_satellite_provisioning = {"foo.bar": "baz"}
        # make sure the task gets dummy rhsm unregister proxy
        rhsm_observer = Mock()
        self.subscription_module._rhsm_observer = rhsm_observer
        # check the task is created correctly
        task_path = self.subscription_interface.UnregisterWithTask()
        obj = check_task_creation(task_path, publisher, UnregisterTask)
        # check all the data got propagated to the module correctly
        assert obj.implementation._registered_to_satellite is True
        assert obj.implementation._rhsm_configuration == {"foo.bar": "baz"}
        assert obj.implementation._rhsm_observer == rhsm_observer
        # trigger the succeeded signal
        obj.implementation.succeeded_signal.emit()
        # check unregistration set the subscription-attached, registered
        # and SCA properties to False
        assert self.subscription_interface.IsRegistered is False
        assert self.subscription_interface.IsRegisteredToSatellite is False
        assert self.subscription_interface.IsSimpleContentAccessEnabled is False
        assert self.subscription_interface.IsSubscriptionAttached is False
        # check the provisioning scrip has been cleared
        assert self.subscription_module._satellite_provisioning_script is None

    @patch_dbus_publish_object
    def test_install_with_tasks_default(self, publisher):
        """Test install tasks - Subscription module in default state."""
        # mock the rhsm config proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        observer.get_proxy.return_value = config_proxy

        task_classes = [
            RestoreRHSMDefaultsTask,
            TransferSubscriptionTokensTask,
            ProvisionTargetSystemForSatelliteTask,
            ConnectToInsightsTask
        ]
        task_paths = self.subscription_interface.InstallWithTasks()
        task_objs = check_task_creation_list(task_paths, publisher, task_classes)

        # RestoreRHSMDefaultsTask
        obj = task_objs[0]
        assert obj.implementation._rhsm_config_proxy == config_proxy

        # TransferSubscriptionTokensTask
        obj = task_objs[1]
        assert obj.implementation._transfer_subscription_tokens is False

        # ProvisionTargetSystemForSatelliteTask
        obj = task_objs[2]
        assert obj.implementation._provisioning_script is None

        # ConnectToInsightsTask
        obj = task_objs[3]
        assert obj.implementation._subscription_attached is False
        assert obj.implementation._connect_to_insights is False

    @patch_dbus_publish_object
    def test_install_with_tasks_configured(self, publisher):
        """Test install tasks - Subscription module in configured state."""

        self.subscription_interface.SetInsightsEnabled(True)
        self.subscription_module.set_subscription_attached(True)
        self.subscription_module.set_registered_to_satellite(True)
        self.subscription_module.set_simple_content_access_enabled(True)
        self.subscription_module._satellite_provisioning_script = "foo script"

        # mock the rhsm config proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        config_proxy = Mock()
        observer.get_proxy.return_value = config_proxy

        task_classes = [
            RestoreRHSMDefaultsTask,
            TransferSubscriptionTokensTask,
            ProvisionTargetSystemForSatelliteTask,
            ConnectToInsightsTask
        ]
        task_paths = self.subscription_interface.InstallWithTasks()
        task_objs = check_task_creation_list(task_paths, publisher, task_classes)

        # RestoreRHSMDefaultsTask
        obj = task_objs[0]
        assert obj.implementation._rhsm_config_proxy == config_proxy

        # TransferSubscriptionTokensTask
        obj = task_objs[1]
        assert obj.implementation._transfer_subscription_tokens is True

        # ProvisionTargetSystemForSatelliteTask
        obj = task_objs[2]
        assert obj.implementation._provisioning_script == "foo script"

        # ConnectToInsightsTask
        obj = task_objs[3]
        assert obj.implementation._subscription_attached is True
        assert obj.implementation._connect_to_insights is True

    def _test_kickstart(self, ks_in, ks_out):
        # mock the rhsm syspurpose proxy that gets requested during
        # the attempt to set system purpose data after a new kickstart has been set
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        syspurpose_proxy = Mock()
        observer.get_proxy.return_value = syspurpose_proxy
        check_kickstart_interface(self.subscription_interface, ks_in, ks_out)

    def test_ks_out_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_ks_out_command_only(self):
        """Test with only syspurpose command being used."""
        ks_in = "syspurpose"
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        # also test resulting module state
        structure = self.subscription_interface.SystemPurposeData
        system_purpose_data = SystemPurposeData.from_structure(structure)
        assert system_purpose_data.role == ""
        assert system_purpose_data.sla == ""
        assert system_purpose_data.usage == ""
        assert system_purpose_data.addons == []

    def test_ks_out_set_role(self):
        """Check kickstart with role being used."""
        ks_in = '''
        syspurpose --role="FOO ROLE"
        '''
        ks_out = '''
        # Intended system purpose\nsyspurpose --role="FOO ROLE"
        '''
        self._test_kickstart(ks_in, ks_out)

    def test_ks_out_set_sla(self):
        """Check kickstart with SLA being used."""
        ks_in = '''
        syspurpose --sla="FOO SLA"
        '''
        ks_out = '''
        # Intended system purpose\nsyspurpose --sla="FOO SLA"
        '''
        self._test_kickstart(ks_in, ks_out)

    def test_ks_out_set_usage(self):
        """Check kickstart with usage being used."""
        ks_in = '''
        syspurpose --usage="FOO USAGE"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --usage="FOO USAGE"
        '''
        self._test_kickstart(ks_in, ks_out)

    def test_ks_out_set_addons(self):
        """Check kickstart with addons being used."""
        ks_in = '''
        syspurpose --addon="Foo Product" --addon="Bar Feature"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --addon="Foo Product" --addon="Bar Feature"
        '''
        self._test_kickstart(ks_in, ks_out)

    def test_ks_out_set_all_usage(self):
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
        assert system_purpose_data.role == 'FOO'
        assert system_purpose_data.sla == 'BAR'
        assert system_purpose_data.usage == 'BAZ'
        assert system_purpose_data.addons == ["F Product", "B Feature"]

    def test_ks_out_rhsm_parse(self):
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
        assert subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        assert subscription_request.organization == "123"
        assert subscription_request.activation_keys.value == []
        # keys should be hidden
        assert subscription_request.activation_keys.type == SECRET_TYPE_HIDDEN
        # account username & password should be empty
        assert subscription_request.account_username == ""
        assert subscription_request.account_password.value == ""
        assert subscription_request.account_password.type == SECRET_TYPE_NONE
        assert subscription_request.server_hostname == "candlepin.foo.com"
        assert subscription_request.rhsm_baseurl == "cdn.foo.com"
        assert subscription_request.server_proxy_hostname == "proxy.com"
        assert subscription_request.server_proxy_port == 9001
        assert subscription_request._server_proxy_user == "user"
        assert subscription_request._server_proxy_password.value == ""
        assert subscription_request._server_proxy_password.type == SECRET_TYPE_HIDDEN

        # insights should be enabled
        assert self.subscription_interface.InsightsEnabled

    def test_ks_out_rhsm_no_insights(self):
        """Check Insights is not enabled from kickstart without --connect-to-insights."""
        ks_in = '''
        rhsm --organization="123" --activation-key="foo_key"
        '''
        # rhsm command is never output as we don't write out activation keys &
        # the command thus would be incomplete resulting in an invalid kickstart
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        # insights should not be
        assert not self.subscription_interface.InsightsEnabled

    def test_ks_out_rhsm_and_syspurpose(self):
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
        assert system_purpose_data.role == 'FOO'
        assert system_purpose_data.sla == 'BAR'
        assert system_purpose_data.usage == 'BAZ'
        assert system_purpose_data.addons == ["F Product", "B Feature"]

        # check subscription request and insights

        structure = self.subscription_interface.SubscriptionRequest
        subscription_request = SubscriptionRequest.from_structure(structure)
        # both org id and one key have been used, request should be org & key type
        assert subscription_request.type == SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        assert subscription_request.organization == "123"
        assert subscription_request.activation_keys.value == []
        assert subscription_request.activation_keys.type == SECRET_TYPE_HIDDEN
        # insights should be enabled
        assert self.subscription_interface.InsightsEnabled

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def test_ks_apply_syspurpose(self, mock_give_purpose):
        """Check that if syspurpose command is used system purpose data is applied."""
        ks_in = '''
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        ks_out = '''
        # Intended system purpose
        syspurpose --role="FOO" --sla="BAR" --usage="BAZ" --addon="F Product" --addon="B Feature"
        '''
        self._test_kickstart(ks_in, ks_out)
        # drill down to the mocked syspurpose proxy
        syspurpose_proxy = self.subscription_module._rhsm_observer.get_proxy.return_value
        # the SystemPurposeConfigurationTask should have been called,
        # which calls give_the_system_purpose()
        mock_give_purpose.assert_called_once_with(sysroot="/",
                                                  rhsm_syspurpose_proxy=syspurpose_proxy,
                                                  role="FOO",
                                                  sla="BAR",
                                                  usage="BAZ",
                                                  addons=['F Product', 'B Feature'])

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def test_ks_no_apply_syspurpose(self, mock_give_purpose):
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

    @patch_dbus_publish_object
    def test_parse_organization_data(self, publisher):
        """Test ParseOrganizationDataTask creation."""
        # make sure the task gets dummy rhsm entitlement and syspurpose proxies

        # prepare the module with dummy data
        full_request = SubscriptionRequest()
        full_request.type = SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD
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
        # make sure the task gets dummy rhsm register server proxy
        observer = Mock()
        observer.get_proxy = Mock()
        self.subscription_module._rhsm_observer = observer
        register_server_proxy = Mock()
        observer.get_proxy.return_value = register_server_proxy

        # check the task is created correctly
        task_path = self.subscription_interface.RetrieveOrganizationsWithTask()
        obj = check_task_creation(task_path, publisher, RetrieveOrganizationsTask)
        # check all the data got propagated to the module correctly
        assert obj.implementation._rhsm_register_server_proxy == register_server_proxy
        assert obj.implementation._username == "foo_user"
        assert obj.implementation._password == "foo_password"
