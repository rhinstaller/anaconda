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
from unittest.mock import patch, Mock, call

import tempfile

from dasbus.typing import get_variant, Str

from pyanaconda.core import util
from pyanaconda.core.constants import SUBSCRIPTION_REQUEST_TYPE_ORG_KEY

from pyanaconda.modules.common.errors.installation import InsightsConnectError, \
    InsightsClientMissingError, SubscriptionTokenTransferError
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest

from pyanaconda.modules.subscription.installation import ConnectToInsightsTask, \
    SystemPurposeConfigurationTask, RestoreRHSMLogLevelTask, \
    TransferSubscriptionTokensTask
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


class TransferSubscriptionTokensTaskTestCase(unittest.TestCase):
    """Test the TransferSubscriptionTokensTask task."""

    def copy_pem_files_test(self):
        """Test PEM file transfer method of the subscription token transfer task."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)

            # input path does not exist
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                self.assertFalse(task._copy_pem_files(input_dir, output_dir))

            # input path is file
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mknod(input_dir)
                self.assertFalse(task._copy_pem_files(input_dir, output_dir))

            # input path directory empty & not_empty=True
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                self.assertFalse(task._copy_pem_files(input_dir, output_dir, not_empty=True))

            # input path directory empty & not_empty=False
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                self.assertTrue(task._copy_pem_files(input_dir, output_dir, not_empty=False))
                # the output dir should have been created and should be empty
                self.assertTrue(os.path.isdir(output_dir))
                self.assertEqual(os.listdir(output_dir), [])

            # test pem file transfer
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                # couple pem files
                os.mknod(os.path.join(input_dir, "foo.pem"))
                os.mknod(os.path.join(input_dir, "bar.pem"))
                os.mknod(os.path.join(input_dir, "baz.pem"))
                # some unrelated files
                os.mknod(os.path.join(input_dir, "something.txt"))
                os.mknod(os.path.join(input_dir, "stuff.conf"))
                # unrelated subfolder
                unrelated_subfolder = os.path.join(input_dir, "unrelated")
                os.mkdir(unrelated_subfolder)
                os.mknod(os.path.join(unrelated_subfolder, "subfolder.pem"))
                os.mknod(os.path.join(unrelated_subfolder, "subfolder.txt"))
                # the method should return True
                self.assertTrue(task._copy_pem_files(input_dir, output_dir, not_empty=True))
                # output folder should contain only the expected pem files
                # - turn the two lists to sets to avoid ordering issues
                self.assertEqual(set(os.listdir(output_dir)),
                                 set(["foo.pem", "bar.pem", "baz.pem"]))

    def copy_file_test(self):
        """Test copy file method of the subscription token transfer task."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)

            # input path does not exist
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                input_file_path = os.path.join(input_dir, "foo.bar")
                output_file_path = os.path.join(output_dir, "foo.bar")
                self.assertFalse(task._copy_file(input_file_path, output_file_path))

            # input path is a directory
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                self.assertFalse(task._copy_file(input_file_path, output_file_path))

            # test file transfer
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output/nested/nested")
                input_file_path = os.path.join(input_dir, "foo.bar")
                output_file_path = os.path.join(output_dir, "foo.bar")
                unrelated_file_path = os.path.join(input_dir, "baz.txt")
                os.mkdir(input_dir)
                os.mknod(input_file_path)
                os.mknod(unrelated_file_path)
                # transfer should succeed
                self.assertTrue(task._copy_file(input_file_path, output_file_path))
                # output file at expected nested path should exist
                output_file_path = os.path.join(output_dir, "foo.bar")
                self.assertTrue(os.path.isfile(output_file_path))
                # otherwise the directory should be empty
                self.assertTrue(os.listdir(output_dir), ["foo.bar"])

    def transfer_file_test(self):
        """Test the transfer file method of the subscription token transfer task."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._copy_file.return_value = True
            task._transfer_file("/etc/foo.conf", "config for FOO")
            sysroot_path = util.join_paths(
                sysroot,
                "/etc/foo.conf"
            )
            task._copy_file.assert_called_once_with(
                "/etc/foo.conf",
                sysroot_path
            )

        # simulate the file not existing
        # - this is a critical error and should raise an exception
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._copy_file.return_value = False
            with self.assertRaises(SubscriptionTokenTransferError):
                task._transfer_file("/etc/foo.conf", "config for FOO")

    @patch("os.path.exists")
    def transfer_system_purpose_test(self, path_exists):
        """Test system purpose transfer method of the subscription token transfer task."""
        # simulate syspurpose file existing
        path_exists.return_value = True
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._transfer_system_purpose()
            sysroot_path = util.join_paths(
                sysroot,
                TransferSubscriptionTokensTask.RHSM_SYSPURPOSE_FILE_PATH
            )
            task._copy_file.assert_called_once_with(
                TransferSubscriptionTokensTask.RHSM_SYSPURPOSE_FILE_PATH,
                sysroot_path
            )

        # simulate syspurpose file not existing
        # - this should result in just the copy operation not being attempted
        path_exists.return_value = False
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._transfer_system_purpose()
            task._copy_file.assert_not_called()

    def transfer_entitlement_keys_test(self):
        """Test the entitlement keys transfer method of the subscription token transfer task."""
        # simulate entitlement keys not existing
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_pem_files = Mock()
            task._copy_pem_files.return_value = True
            task._transfer_entitlement_keys()
            sysroot_path = util.join_paths(
                sysroot,
                TransferSubscriptionTokensTask.RHSM_ENTITLEMENT_KEYS_PATH
            )
            task._copy_pem_files.assert_called_once_with(
                TransferSubscriptionTokensTask.RHSM_ENTITLEMENT_KEYS_PATH,
                sysroot_path
            )

        # simulate entitlement keys not existing
        # - this is a critical error and should raise an exception
        #   (without proper certificates and keys the target system
        #    would be unable to communicate with the Red Hat subscription
        #    infrastructure)
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_pem_files = Mock()
            task._copy_pem_files.return_value = False
            with self.assertRaises(SubscriptionTokenTransferError):
                task._transfer_entitlement_keys()

    def transfer_test(self):
        """Test transfer_tokens being True is handled correctly for token transfer task."""

        # If transfer_subscription_tokens is True, all token should be transferred.
        # As we test each transfer method individually we just check here that all
        # expected method are called.

        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._transfer_system_purpose = Mock()
            task._transfer_entitlement_keys = Mock()
            task._transfer_file = Mock()
            # run the task
            task.run()
            # all the transfer operations should have been done
            task._transfer_system_purpose.assert_called_once()
            task._transfer_entitlement_keys.assert_called_once()
            task._transfer_file.assert_has_calls(
                [call('/etc/pki/consumer/key.pem', 'RHSM consumer key'),
                 call('/etc/pki/consumer/cert.pem', 'RHSM consumer cert'),
                 call('/etc/yum.repos.d/redhat.repo', 'RHSM repo file'),
                 call('/etc/rhsm/rhsm.conf', 'RHSM config file')]
            )

    def no_transfer_test(self):
        """Test transfer_tokens being False is handled correctly for token transfer task."""

        # if transfer_subscription_tokens is False, only system purpose tokens should be
        # transferred and others ignored

        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=False)
            task._transfer_system_purpose = Mock()
            task._transfer_entitlement_keys = Mock()
            task._transfer_file = Mock()
            # run the task
            task.run()
            # only the system purpose transfer method should have been called
            task._transfer_system_purpose.assert_called_once()
            task._transfer_entitlement_keys.assert_not_called()
            task._transfer_file.assert_not_called()
