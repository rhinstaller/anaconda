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
from unittest.mock import patch, Mock

import tempfile

from dasbus.typing import get_variant, Str

from pyanaconda.core import util
from pyanaconda.core.constants import SUBSCRIPTION_REQUEST_TYPE_ORG_KEY

from pyanaconda.modules.common.errors.installation import InsightsConnectError, \
    InsightsClientMissingError
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest

from pyanaconda.modules.subscription.installation import ConnectToInsightsTask, \
    SystemPurposeConfigurationTask, RestoreRHSMLogLevelTask
from pyanaconda.modules.subscription.runtime import SetRHSMConfigurationTask

class ConnectToInsightsTaskTestCase(unittest.TestCase):
    """Test the ConnectToInsights task."""

    @patch("pyanaconda.core.util.execWithRedirect")
    def no_connect_test(self, exec_with_redirect):
        """Test that nothing is done if Insights connection is not requested."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=False,
                                         connect_to_insights=False)
            task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def not_subscribed_test(self, exec_with_redirect):
        """Test that nothing is done if Insights is requested but system is not subscribed."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=False,
                                         connect_to_insights=True)
            task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def utility_not_available_test(self, exec_with_redirect):
        """Test that the client-missing exception is raised if Insights client is missing."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=True,
                                         connect_to_insights=True)
            with self.assertRaises(InsightsClientMissingError):
                task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def connect_error_test(self, exec_with_redirect):
        """Test that the expected exception is raised if the Insights client fails when called."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create a fake insights client tool file
            utility_path = ConnectToInsightsTask.INSIGHTS_TOOL_PATH
            directory = os.path.split(utility_path)[0]
            os.makedirs(util.join_paths(sysroot, directory))
            os.mknod(util.join_paths(sysroot, utility_path))
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=True,
                                         connect_to_insights=True)
            # make sure execWithRedirect has a non zero return code
            exec_with_redirect.return_value = 1
            with self.assertRaises(InsightsConnectError):
                task.run()
            # check that call to the insights client has been done with the expected parameters
            exec_with_redirect.assert_called_once_with('/usr/bin/insights-client',
                                                       ['--register'],
                                                       root=sysroot)

    @patch("pyanaconda.core.util.execWithRedirect")
    def connect_test(self, exec_with_redirect):
        """Test that it is possible to connect to Insights."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create a fake insights client tool file
            utility_path = ConnectToInsightsTask.INSIGHTS_TOOL_PATH
            directory = os.path.split(utility_path)[0]
            # we use + here instead of os.path.join() as both paths are absolute and
            # os.path.join() does not handle that very well
            os.makedirs(sysroot + directory)
            os.mknod(sysroot + utility_path)
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=True,
                                         connect_to_insights=True)
            # make sure execWithRedirect has a zero return code
            exec_with_redirect.return_value = 0
            task.run()
            # check that call to the insights client has been done with the expected parameters
            exec_with_redirect.assert_called_once_with('/usr/bin/insights-client',
                                                       ['--register'],
                                                       root=sysroot)


class SystemPurposeConfigurationTaskTestCase(unittest.TestCase):
    """Test the SystemPurposeConfigurationTask task.

    As we test the give_system_purpose() method quite extensively,
    just making sure it is called correctly by the task should be
    enough here.
    """

    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def system_purpose_task_test(self, give_the_system_purpose):
        """Test the SystemPurposeConfigurationTask task."""
        with tempfile.TemporaryDirectory() as sysroot:
            system_purpose_data = SystemPurposeData()
            system_purpose_data.role = "foo"
            system_purpose_data.sla = "bar"
            system_purpose_data.usage = "baz"
            system_purpose_data.addons = ["a", "b", "c"]
            task = SystemPurposeConfigurationTask(sysroot, system_purpose_data)
            task.run()
            give_the_system_purpose.assert_called_once_with(role="foo",
                                                            sla="bar",
                                                            usage="baz",
                                                            addons=["a", "b", "c"],
                                                            sysroot=sysroot)


class SetRHSMConfigurationTaskTestCase(unittest.TestCase):
    """Test the SystemPurposeConfigurationTask task.

    We mainly need to test that the task attempts to set the correct
    values to the (mock) RHSM config DBus interface, including values
    help in SecretData instances. Also it needs to be able reset
    keys to default values if they come in blank.
    """

    def set_rhsm_config_tast_test(self):
        """Test the SetRHSMConfigurationTask task."""
        mock_config_proxy = Mock()
        # RHSM config default values
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
        # a representative subscription request
        request = SubscriptionRequest()
        request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        request.organization = "123456789"
        request.account_username = "foo_user"
        request.server_hostname = "candlepin.foo.com"
        request.rhsm_baseurl = "cdn.foo.com"
        request.server_proxy_hostname = "proxy.foo.com"
        request.server_proxy_port = 9001
        request.server_proxy_user = "foo_proxy_user"
        request.account_password.set_secret("foo_password")
        request.activation_keys.set_secret(["key1", "key2", "key3"])
        request.server_proxy_password.set_secret("foo_proxy_password")
        # create a task
        task = SetRHSMConfigurationTask(rhsm_config_proxy=mock_config_proxy,
                                        rhsm_config_defaults=default_config,
                                        subscription_request=request)
        task.run()
        # check that we tried to set the expected config keys via the RHSM config DBus API
        expected_dict = {"server.hostname": get_variant(Str, "candlepin.foo.com"),
                         "server.proxy_hostname": get_variant(Str, "proxy.foo.com"),
                         "server.proxy_port": get_variant(Str, "9001"),
                         "server.proxy_user": get_variant(Str, "foo_proxy_user"),
                         "server.proxy_password": get_variant(Str, "foo_proxy_password"),
                         "rhsm.baseurl": get_variant(Str, "cdn.foo.com")}

        mock_config_proxy.SetAll.assert_called_once_with(expected_dict, "")

    def set_rhsm_config_tast_restore_default_value_test(self):
        """Test the SetRHSMConfigurationTask task - restore default values."""
        mock_config_proxy = Mock()
        # RHSM config default values
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
        # a representative subscription request, with server hostname and rhsm baseurl
        # set to blank
        request = SubscriptionRequest()
        request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        request.organization = "123456789"
        request.account_username = "foo_user"
        request.server_hostname = ""
        request.rhsm_baseurl = ""
        request.server_proxy_hostname = "proxy.foo.com"
        request.server_proxy_port = 9001
        request.server_proxy_user = "foo_proxy_user"
        request.account_password.set_secret("foo_password")
        request.activation_keys.set_secret(["key1", "key2", "key3"])
        request.server_proxy_password.set_secret("foo_proxy_password")
        # create a task
        task = SetRHSMConfigurationTask(rhsm_config_proxy=mock_config_proxy,
                                        rhsm_config_defaults=default_config,
                                        subscription_request=request)
        task.run()
        # check that the server.hostname and rhsm.baseurl keys are set
        # to the default value
        expected_dict = {"server.hostname": get_variant(Str, "server.example.com"),
                         "server.proxy_hostname": get_variant(Str, "proxy.foo.com"),
                         "server.proxy_port": get_variant(Str, "9001"),
                         "server.proxy_user": get_variant(Str, "foo_proxy_user"),
                         "server.proxy_password": get_variant(Str, "foo_proxy_password"),
                         "rhsm.baseurl": get_variant(Str, "cdn.example.com")}

        mock_config_proxy.SetAll.assert_called_once_with(expected_dict, "")


class RestoreRHSMLogLevelTaskTestCase(unittest.TestCase):
    """Test the RestoreRHSMLogLevelTask task."""

    def restore_rhsm_log_level_task_test(self):
        """Test the RestoreRHSMLogLevelTask task."""
        mock_config_proxy = Mock()
        task = RestoreRHSMLogLevelTask(rhsm_config_proxy=mock_config_proxy)
        task.run()
        mock_config_proxy.Set.assert_called_once_with("logging.default_log_level",
                                                      get_variant(Str, "INFO"),
                                                      "")
