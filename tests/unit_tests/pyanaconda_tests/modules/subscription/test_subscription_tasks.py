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
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import gi
import pytest
from dasbus.error import DBusError
from dasbus.typing import Bool, Str, get_native, get_variant

from pyanaconda.core.constants import (
    RHSM_SYSPURPOSE_FILE_PATH,
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD,
)
from pyanaconda.core.path import join_paths
from pyanaconda.modules.common.constants.objects import (
    RHSM_CONFIG,
    RHSM_REGISTER,
    RHSM_UNREGISTER,
)
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.errors.installation import (
    InsightsClientMissingError,
    InsightsConnectError,
    SubscriptionTokenTransferError,
)
from pyanaconda.modules.common.errors.subscription import (
    MultipleOrganizationsError,
    RegistrationError,
    SatelliteProvisioningError,
)
from pyanaconda.modules.common.structures.subscription import (
    OrganizationData,
    SubscriptionRequest,
    SystemPurposeData,
)
from pyanaconda.modules.subscription.constants import (
    RHSM_SERVICE_NAME,
    SERVER_HOSTNAME_NOT_SATELLITE_PREFIX,
)
from pyanaconda.modules.subscription.installation import (
    ConnectToInsightsTask,
    ProvisionTargetSystemForSatelliteTask,
    RestoreRHSMDefaultsTask,
    TransferSubscriptionTokensTask,
)
from pyanaconda.modules.subscription.runtime import (
    BackupRHSMConfBeforeSatelliteProvisioningTask,
    DownloadSatelliteProvisioningScriptTask,
    ParseSubscriptionDataTask,
    RegisterAndSubscribeTask,
    RegisterWithOrganizationKeyTask,
    RegisterWithUsernamePasswordTask,
    RetrieveOrganizationsTask,
    RHSMPrivateBus,
    RollBackSatelliteProvisioningTask,
    RunSatelliteProvisioningScriptTask,
    SetRHSMConfigurationTask,
    SystemPurposeConfigurationTask,
    UnregisterTask,
)

gi.require_version("Gio", "2.0")
from gi.repository import Gio


class ConnectToInsightsTaskTestCase(unittest.TestCase):
    """Test the ConnectToInsights task."""

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_no_connect(self, exec_with_redirect):
        """Test that nothing is done if Insights connection is not requested."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=False,
                                         connect_to_insights=False)
            task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_not_subscribed(self, exec_with_redirect):
        """Test that nothing is done if Insights is requested but system is not subscribed."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=False,
                                         connect_to_insights=True)
            task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_utility_not_available(self, exec_with_redirect):
        """Test that the client-missing exception is raised if Insights client is missing."""

        with tempfile.TemporaryDirectory() as sysroot:
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=True,
                                         connect_to_insights=True)
            with pytest.raises(InsightsClientMissingError):
                task.run()
            # check that no attempt to call the Insights client has been attempted
            exec_with_redirect.assert_not_called()

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_connect_error(self, exec_with_redirect):
        """Test that the expected exception is raised if the Insights client fails when called."""
        with tempfile.TemporaryDirectory() as sysroot:
            # create a fake insights client tool file
            utility_path = ConnectToInsightsTask.INSIGHTS_TOOL_PATH
            directory = os.path.split(utility_path)[0]
            os.makedirs(join_paths(sysroot, directory))
            os.mknod(join_paths(sysroot, utility_path))
            task = ConnectToInsightsTask(sysroot=sysroot,
                                         subscription_attached=True,
                                         connect_to_insights=True)
            # make sure execWithRedirect has a non zero return code
            exec_with_redirect.return_value = 1
            with pytest.raises(InsightsConnectError):
                task.run()
            # check that call to the insights client has been done with the expected parameters
            exec_with_redirect.assert_called_once_with('/usr/bin/insights-client',
                                                       ['--register'],
                                                       root=sysroot)

    @patch("pyanaconda.core.util.execWithRedirect")
    def test_connect(self, exec_with_redirect):
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
    def test_system_purpose_task(self, give_the_system_purpose):
        """Test the SystemPurposeConfigurationTask task - not yet set."""
        # prepare some system purpose data
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]
        # create a mock syspurpose proxy
        syspurpose_proxy = Mock()
        task = SystemPurposeConfigurationTask(syspurpose_proxy, system_purpose_data)
        task.run()
        give_the_system_purpose.assert_called_once_with(sysroot="/",
                                                        rhsm_syspurpose_proxy=syspurpose_proxy,
                                                        role="foo",
                                                        sla="bar",
                                                        usage="baz",
                                                        addons=["a", "b", "c"])

    @patch("pyanaconda.core.subscription.check_system_purpose_set")
    @patch("pyanaconda.modules.subscription.system_purpose.give_the_system_purpose")
    def test_system_purpose_task_already_set(self, give_the_system_purpose, check_set):
        """Test the SystemPurposeConfigurationTask task - already set."""
        # The task should still run give_the_system_purpose() even if system purpose
        # has already been set to make it possible to overwrite or clear existing data.
        check_set.return_value = True
        # prepare some system purpose data
        system_purpose_data = SystemPurposeData()
        system_purpose_data.role = "foo"
        system_purpose_data.sla = "bar"
        system_purpose_data.usage = "baz"
        system_purpose_data.addons = ["a", "b", "c"]
        # create a mock syspurpose proxy
        syspurpose_proxy = Mock()
        task = SystemPurposeConfigurationTask(syspurpose_proxy, system_purpose_data)
        task.run()
        give_the_system_purpose.assert_called_once_with(sysroot="/",
                                                        rhsm_syspurpose_proxy=syspurpose_proxy,
                                                        role="foo",
                                                        sla="bar",
                                                        usage="baz",
                                                        addons=["a", "b", "c"])


class SetRHSMConfigurationTaskTestCase(unittest.TestCase):
    """Test the SystemPurposeConfigurationTask task.

    We mainly need to test that the task attempts to set the correct
    values to the (mock) RHSM config DBus interface, including values
    help in SecretData instances. Also it needs to be able reset
    keys to default values if they come in blank.
    """

    def test_set_rhsm_config_tast(self):
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

    def test_set_rhsm_config_tast_restore_default_value(self):
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

    def test_set_rhsm_config_task_not_satellite(self):
        """Test the SetRHSMConfigurationTask task - not-satellite prefix handling."""
        # if the subscription request has the no-satellite prefix, it should be stripped
        # before the server hostname value is sent to RHSM
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
        request.server_hostname = "not-satellite:candlepin.foo.com"
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


class RestoreRHSMDefaultsTaskTestCase(unittest.TestCase):
    """Test the RestoreRHSMDefaultsTask task."""

    def test_restore_rhsm_log_level_task(self):
        """Test the RestoreRHSMDefaultsTask task."""
        mock_config_proxy = Mock()
        task = RestoreRHSMDefaultsTask(rhsm_config_proxy=mock_config_proxy)
        task.run()
        mock_config_proxy.SetAll.assert_called_once_with({
            "logging.default_log_level": get_variant(Str, "INFO"),
            "server.insecure": get_variant(Str, "0")
        }, "")


class TransferSubscriptionTokensTaskTestCase(unittest.TestCase):
    """Test the TransferSubscriptionTokensTask task."""

    def test_copy_pem_files(self):
        """Test PEM file transfer method of the subscription token transfer task."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)

            # input path does not exist
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                assert not task._copy_pem_files(input_dir, output_dir)

            # input path is file
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mknod(input_dir)
                assert not task._copy_pem_files(input_dir, output_dir)

            # input path directory empty & not_empty=True
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                assert not task._copy_pem_files(input_dir, output_dir, not_empty=True)

            # input path directory empty & not_empty=False
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                assert task._copy_pem_files(input_dir, output_dir, not_empty=False)
                # the output dir should have been created and should be empty
                assert os.path.isdir(output_dir)
                assert os.listdir(output_dir) == []

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
                assert task._copy_pem_files(input_dir, output_dir, not_empty=True)
                # output folder should contain only the expected pem files
                # - turn the two lists to sets to avoid ordering issues
                assert set(os.listdir(output_dir)) == \
                    set(["foo.pem", "bar.pem", "baz.pem"])

    def test_copy_file(self):
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
                assert not task._copy_file(input_file_path, output_file_path)

            # input path is a directory
            with tempfile.TemporaryDirectory() as tempdir:
                input_dir = os.path.join(tempdir, "input")
                output_dir = os.path.join(tempdir, "output")
                os.mkdir(input_dir)
                assert not task._copy_file(input_file_path, output_file_path)

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
                assert task._copy_file(input_file_path, output_file_path)
                # output file at expected nested path should exist
                output_file_path = os.path.join(output_dir, "foo.bar")
                assert os.path.isfile(output_file_path)
                # otherwise the directory should be empty
                assert os.listdir(output_dir), ["foo.bar"]

    def test_transfer_file(self):
        """Test the transfer file method of the subscription token transfer task."""
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._copy_file.return_value = True
            task._transfer_file("/etc/foo.conf", "config for FOO")
            sysroot_path = join_paths(
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
            with pytest.raises(SubscriptionTokenTransferError):
                task._transfer_file("/etc/foo.conf", "config for FOO")

    @patch("os.path.exists")
    def test_transfer_system_purpose(self, path_exists):
        """Test system purpose transfer method of the subscription token transfer task."""
        # simulate syspurpose file existing
        path_exists.return_value = True
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_file = Mock()
            task._transfer_system_purpose()
            sysroot_path = join_paths(
                sysroot,
                RHSM_SYSPURPOSE_FILE_PATH
            )
            task._copy_file.assert_called_once_with(
                RHSM_SYSPURPOSE_FILE_PATH,
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

    def test_transfer_entitlement_keys(self):
        """Test the entitlement keys transfer method of the subscription token transfer task."""
        # simulate entitlement keys not existing
        with tempfile.TemporaryDirectory() as sysroot:
            task = TransferSubscriptionTokensTask(sysroot=sysroot,
                                                  transfer_subscription_tokens=True)
            task._copy_pem_files = Mock()
            task._copy_pem_files.return_value = True
            task._transfer_entitlement_keys()
            sysroot_path = join_paths(
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
            with pytest.raises(SubscriptionTokenTransferError):
                task._transfer_entitlement_keys()

    def test_transfer(self):
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

    def test_no_transfer(self):
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


class RHSMPrivateBusTestCase(unittest.TestCase):
    """Test the RHSMPrivateBus class.

    This class provides access to the RHSM private bus and also
    implements context manager API for easy use.
    """

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_rhsm_private_bus(self, environ_get):
        """Test the RHSMPrivateBus class."""
        # mock the register server proxy
        register_server_proxy = Mock()
        mock_address = "abcdefgh"
        register_server_proxy.Start.return_value = mock_address
        # prepare a mock bus backend now so we can check later that
        # disconnect() was called after exiting the context manager
        provider = Mock()
        disconnect = Mock()
        get_address_bus = provider.get_addressed_bus_connection
        connection = get_address_bus.return_value
        # enter the context manager
        with RHSMPrivateBus(register_server_proxy) as private_bus:
            # the private bus address should be set once we are
            # inside the context of the context manager
            assert private_bus._private_bus_address == mock_address
            # the register server proxy Start method should have been called
            register_server_proxy.Start.assert_called_once_with("en_US.UTF-8")
            # now mock the backend of the bus instance to prevent it from
            # trying to get an actual connection
            private_bus._provider = provider
            # also mock the disconnect method so we can check it was called
            private_bus.disconnect = disconnect
            # and try to get a proxy
            private_register_proxy = private_bus.connection.get_proxy(RHSM.service_name,
                                                                      RHSM_REGISTER.object_path)
            # check correct address was used
            get_address_bus.assert_called_with(
                bus_address="abcdefgh",
                flags=Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            )

            # check correct proxy was requested from the connection
            connection.get_proxy.assert_called_once_with(RHSM.service_name,
                                                         RHSM_REGISTER.object_path)
            assert private_register_proxy == connection.get_proxy.return_value
        # exit the context manager and check cleanup happened as expected
        disconnect.assert_called_once()
        register_server_proxy.Stop.assert_called_once_with("en_US.UTF-8")


class RegistrationTasksTestCase(unittest.TestCase):
    """Test the registration tasks."""

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_username_password_success(self, private_bus, environ_get):
        """Test the RegisterWithUsernamePasswordTask - success."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # make the Register() method return some JSON data
        private_register_proxy.Register.return_value = '{"json":"stuff"}'
        # instantiate the task and run it
        task = RegisterWithUsernamePasswordTask(rhsm_register_server_proxy=register_server_proxy,
                                                username="foo_user",
                                                password="bar_password",
                                                organization="foo_org")
        assert task.run() == '{"json":"stuff"}'
        # check the private register proxy Register method was called correctly
        private_register_proxy.Register.assert_called_once_with(
            "foo_org",
            "foo_user",
            "bar_password",
            {"enable_content": get_variant(Bool, True)},
            {},
            "en_US.UTF-8"
        )

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_username_password_failure(self, private_bus, environ_get):
        """Test the RegisterWithUsernamePasswordTask - failure."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # raise DBusError with error message in JSON
        json_error = '{"message": "Registration failed."}'
        private_register_proxy.Register.side_effect = DBusError(json_error)
        # instantiate the task and run it
        task = RegisterWithUsernamePasswordTask(rhsm_register_server_proxy=register_server_proxy,
                                                username="foo_user",
                                                password="bar_password",
                                                organization="foo_org")
        with pytest.raises(RegistrationError):
            task.run()
        # check private register proxy Register method was called correctly
        private_register_proxy.Register.assert_called_with(
            "foo_org",
            "foo_user",
            "bar_password",
            {"enable_content": get_variant(Bool, True)},
            {},
            "en_US.UTF-8"
        )

    @patch("pyanaconda.modules.subscription.runtime.RetrieveOrganizationsTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_username_password_org_single(self, private_bus, environ_get, retrieve_orgs_task):
        """Test the RegisterWithUsernamePasswordTask - parsed single org."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # make the Register() method return some JSON data
        private_register_proxy.Register.return_value = '{"json":"stuff"}'
        # mock the org data retrieval task to return single organization
        org_data = [
            {
                "key": "foo_org",
                "displayName": "Foo Org",
            }
        ]
        org_data_json = json.dumps(org_data)
        org_data_list = RetrieveOrganizationsTask._parse_org_data_json(org_data_json)
        retrieve_orgs_task.return_value.run.return_value = org_data_list
        # prepare mock data callaback as well
        # instantiate the task and run it - we set organization to "" to make the task
        # fetch organization list
        task = RegisterWithUsernamePasswordTask(rhsm_register_server_proxy=register_server_proxy,
                                                username="foo_user",
                                                password="bar_password",
                                                organization="")
        # if we get just a single organization, we don't actually have to feed
        # it to the RHSM API, its only a problem if there are more than one
        assert task.run() == '{"json":"stuff"}'
        # check the private register proxy Register method was called correctly
        private_register_proxy.Register.assert_called_once_with(
            "",
            "foo_user",
            "bar_password",
            {"enable_content": get_variant(Bool, True)},
            {},
            "en_US.UTF-8"
        )

    @patch("pyanaconda.modules.subscription.runtime.RetrieveOrganizationsTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_username_password_org_multi(self, environ_get, retrieve_orgs_task):
        """Test the RegisterWithUsernamePasswordTask - parsed multiple orgs."""
        # register server proxy
        register_server_proxy = Mock()
        # mock the org data retrieval task to return single organization
        org_data = [
            {
                "key": "foo_org",
                "displayName": "Foo Org",
            },
            {
                "key": "bar_org",
                "displayName": "Bar Org",
            },
            {
                "key": "baz_org",
                "displayName": "Baz Org",
            }
        ]
        org_data_json = json.dumps(org_data)
        org_data_list = RetrieveOrganizationsTask._parse_org_data_json(org_data_json)
        retrieve_orgs_task.return_value.run.return_value = org_data_list
        # instantiate the task and run it - we set organization to "" to make the task
        # fetch organization list
        task = RegisterWithUsernamePasswordTask(rhsm_register_server_proxy=register_server_proxy,
                                                username="foo_user",
                                                password="bar_password",
                                                organization="")
        # if we get more than one organization, we can's automatically decide which one to
        # use so we throw an exception to notify the user to pick one and try again
        with pytest.raises(MultipleOrganizationsError):
            task.run()

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_org_key_success(self, private_bus, environ_get):
        """Test the RegisterWithOrganizationKeyTask - success."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        private_register_proxy.Register.return_value = True, ""
        # make the Register() method return some JSON data
        private_register_proxy.RegisterWithActivationKeys.return_value = '{"json":"stuff"}'
        # instantiate the task and run it
        task = RegisterWithOrganizationKeyTask(rhsm_register_server_proxy=register_server_proxy,
                                               organization="123456789",
                                               activation_keys=["foo", "bar", "baz"])
        assert task.run() == '{"json":"stuff"}'
        # check private register proxy RegisterWithActivationKeys method was called correctly
        private_register_proxy.RegisterWithActivationKeys.assert_called_with(
            "123456789",
            ["foo", "bar", "baz"],
            {},
            {},
            'en_US.UTF-8'
        )

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_org_key_failure(self, private_bus, environ_get):
        """Test the RegisterWithOrganizationKeyTask - failure."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # raise DBusError with error message in JSON
        json_error = '{"message": "Registration failed."}'
        private_register_proxy.RegisterWithActivationKeys.side_effect = DBusError(json_error)
        # instantiate the task and run it
        task = RegisterWithOrganizationKeyTask(rhsm_register_server_proxy=register_server_proxy,
                                               organization="123456789",
                                               activation_keys=["foo", "bar", "baz"])
        with pytest.raises(RegistrationError):
            task.run()
        # check private register proxy RegisterWithActivationKeys method was called correctly
        private_register_proxy.RegisterWithActivationKeys.assert_called_with(
            "123456789",
            ["foo", "bar", "baz"],
            {},
            {},
            'en_US.UTF-8'
        )


class UnregisterTaskTestCase(unittest.TestCase):
    """Test the unregister task."""

    @patch("pyanaconda.modules.subscription.runtime.RollBackSatelliteProvisioningTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_success(self, environ_get, roll_back_task):
        """Test the UnregisterTask - success."""
        rhsm_observer = Mock()
        # instantiate the task and run it
        task = UnregisterTask(
            rhsm_observer=rhsm_observer,
            registered_to_satellite=False,
            rhsm_configuration={}
        )
        task.run()
        # check the unregister proxy Unregister method was called correctly
        rhsm_observer.get_proxy.assert_called_once_with(RHSM_UNREGISTER)
        # registered_to_satellite is False, so roll back task should not run
        roll_back_task.assert_not_called()
        roll_back_task.return_value.run.assert_not_called()

    @patch("pyanaconda.modules.subscription.runtime.RollBackSatelliteProvisioningTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_failure(self, environ_get, roll_back_task):
        """Test the UnregisterTask - failure."""
        rhsm_observer = Mock()
        rhsm_unregister_proxy = rhsm_observer.get_proxy.return_value
        # raise DBusError with error message in JSON
        json_error = '{"message": "Unregistration failed."}'
        rhsm_unregister_proxy.Unregister.side_effect = DBusError(json_error)
        # instantiate the task and run it
        task = UnregisterTask(
            rhsm_observer=rhsm_observer,
            registered_to_satellite=False,
            rhsm_configuration={}
        )
        with pytest.raises(DBusError):
            task.run()
        # check the RHSM observer was used correctly
        rhsm_observer.get_proxy.assert_called_once_with(RHSM_UNREGISTER)
        # check the unregister proxy Unregister method was called correctly
        rhsm_unregister_proxy.Unregister.assert_called_once_with({}, "en_US.UTF-8")
        # registered_to_satellite is False, so roll back task should not run
        roll_back_task.assert_not_called()
        roll_back_task.return_value.run.assert_not_called()

    @patch("pyanaconda.modules.subscription.runtime.RollBackSatelliteProvisioningTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_failure_satellite(self, environ_get, roll_back_task):
        """Test the UnregisterTask - unregister failure on Satellite."""
        rhsm_observer = Mock()
        rhsm_unregister_proxy = rhsm_observer.get_proxy.return_value
        # raise DBusError with error message in JSON
        json_error = '{"message": "Unregistration failed."}'
        rhsm_unregister_proxy.Unregister.side_effect = DBusError(json_error)
        # instantiate the task and run it
        task = UnregisterTask(
            rhsm_observer=rhsm_observer,
            registered_to_satellite=True,
            rhsm_configuration={}
        )
        with pytest.raises(DBusError):
            task.run()
        # check the RHSM observer was used correctly
        rhsm_observer.get_proxy.assert_called_once_with(RHSM_UNREGISTER)
        # check the unregister proxy Unregister method was called correctly
        rhsm_unregister_proxy.Unregister.assert_called_once_with({}, "en_US.UTF-8")
        # registered_to_satellite is True, but unregistration failed before roll back
        # could happen
        roll_back_task.assert_not_called()
        roll_back_task.return_value.run.assert_not_called()

    @patch("pyanaconda.modules.subscription.runtime.RollBackSatelliteProvisioningTask")
    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_satellite_success(self, environ_get, roll_back_task):
        """Test the UnregisterTask - Satellite rollback success."""
        rhsm_observer = Mock()
        unregister_proxy = Mock()
        config_proxy = Mock()
        rhsm_observer.get_proxy.side_effect = [unregister_proxy, config_proxy]
        # instantiate the task and run it
        mock_rhsm_configuration = {"foo": "bar"}
        task = UnregisterTask(
            rhsm_observer=rhsm_observer,
            registered_to_satellite=True,
            rhsm_configuration=mock_rhsm_configuration
        )
        task.run()
        # check the unregister proxy Unregister method was called correctly
        rhsm_observer.get_proxy.assert_has_calls([])
        # registered_to_satellite is False, so roll back task should not run
        roll_back_task.assert_called_once_with(rhsm_config_proxy=config_proxy,
                                               rhsm_configuration=mock_rhsm_configuration)
        roll_back_task.return_value.run.assert_called_once()


class ParseSubscriptionDataTaskTestCase(unittest.TestCase):
    """Test the attached subscription parsing task."""

    def test_system_purpose_json_parsing(self):
        """Test the system purpose JSON parsing method of ParseSubscriptionDataTask."""
        parse_method = ParseSubscriptionDataTask._parse_system_purpose_json
        # the parsing method should be able to survive also getting an empty string
        expected_struct = {
            "role": "",
            "sla": "",
            "usage": "",
            "addons": []
        }
        struct = get_native(
            SystemPurposeData.to_structure(parse_method(""))
        )
        assert struct == expected_struct
        # try parsing expected complete system purpose data
        system_purpose_dict = {
            "role": "important",
            "service_level_agreement": "it will work just fine",
            "usage": "careful",
            "addons": ["red", "green", "blue"]
        }
        system_purpose_json = json.dumps(system_purpose_dict)
        expected_struct = {
            "role": "important",
            "sla": "it will work just fine",
            "usage": "careful",
            "addons": ["red", "green", "blue"]
        }
        struct = get_native(
            SystemPurposeData.to_structure(parse_method(system_purpose_json))
        )
        assert struct == expected_struct
        # try also partial parsing, just in case
        system_purpose_dict = {
            "role": "important",
            "usage": "careful",
        }
        system_purpose_json = json.dumps(system_purpose_dict)
        expected_struct = {
            "role": "important",
            "sla": "",
            "usage": "careful",
            "addons": []
        }
        struct = get_native(
            SystemPurposeData.to_structure(parse_method(system_purpose_json))
        )
        assert struct == expected_struct

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_attach_subscription_task_success(self, environ_get):
        """Test the ParseSubscriptionDataTask."""
        # prepare mock proxies the task is expected to interact with
        rhsm_syspurpose_proxy = Mock()
        rhsm_syspurpose_proxy.GetSyspurpose.return_value = "bar"
        task = ParseSubscriptionDataTask(rhsm_syspurpose_proxy=rhsm_syspurpose_proxy)
        # mock the parsing methods
        system_purpose_data = SystemPurposeData()
        task._parse_system_purpose_json = Mock()
        task._parse_system_purpose_json.return_value = system_purpose_data
        # run the task
        result = task.run()
        # check DBus proxies were called as expected
        rhsm_syspurpose_proxy.GetSyspurpose.assert_called_once_with("en_US.UTF-8")
        # check the parsing methods were called
        task._parse_system_purpose_json.assert_called_once_with("bar")
        # check the result that has been returned is as expected
        assert result.system_purpose_data == system_purpose_data


class SatelliteTasksTestCase(unittest.TestCase):
    """Test the Satellite support tasks."""

    @patch("pyanaconda.modules.subscription.satellite.download_satellite_provisioning_script")
    def test_satellite_provisioning_script_download(self, download_function):
        """Test the DownloadSatelliteProvisioningScriptTask."""
        # make the download function return a dummy script text
        download_function.return_value = "foo bar"
        # create the task and run it
        task = DownloadSatelliteProvisioningScriptTask(
            satellite_url="satellite.example.com",
            proxy_url="proxy.example.com",
        )
        assert task.run() == "foo bar"
        # check the wrapped download function was called correctly
        download_function.assert_called_with(
            satellite_url="satellite.example.com",
            proxy_url="proxy.example.com",
        )

    @patch("pyanaconda.modules.subscription.satellite.run_satellite_provisioning_script")
    def test_satellite_provisioning_run_script(self, run_script_function):
        """Test the RunSatelliteProvisioningScriptTask - success."""
        # create the task and run it
        task = RunSatelliteProvisioningScriptTask(
            provisioning_script="foo bar"
        )
        task.run()
        # check the wrapped run function was called correctly
        run_script_function.assert_called_with(
            provisioning_script="foo bar",
            run_on_target_system=False
        )

    @patch("pyanaconda.modules.subscription.satellite.run_satellite_provisioning_script")
    def test_satellite_provisioning_run_script_failure(self, run_script_function):
        """Test the RunSatelliteProvisioningScriptTask - failure."""
        # make sure the run-script function raises the correct error
        run_script_function.side_effect = SatelliteProvisioningError()
        # create the task and run it
        task = RunSatelliteProvisioningScriptTask(
            provisioning_script="foo bar"
        )
        with pytest.raises(SatelliteProvisioningError):
            task.run()
        # check the wrapped run function was called correctly
        run_script_function.assert_called_with(
            provisioning_script="foo bar",
            run_on_target_system=False
        )

    def test_rhsm_config_backup(self):
        """Test the BackupRHSMConfBeforeSatelliteProvisioningTask."""
        # create mock RHSM config proxy
        config_proxy = Mock()
        # make it return a DBus struct
        config_proxy.GetAll.return_value = {"foo": get_variant(Str, "bar")}
        # create the task and run it
        task = BackupRHSMConfBeforeSatelliteProvisioningTask(
            rhsm_config_proxy=config_proxy
        )
        conf_backup = task.run()
        # check the RHSM config proxy was called correctly
        config_proxy.GetAll.assert_called_once_with("")
        # check the DBus struct is correctly converted to a Python dict
        assert conf_backup == {"foo": "bar"}

    def test_rhsm_roll_back(self):
        """Test the RollBackSatelliteProvisioningTask."""
        # create mock RHSM config proxy
        config_proxy = Mock()
        # and mock RHSM configuration
        rhsm_config = {"foo": "bar"}
        # create the task and run it
        task = RollBackSatelliteProvisioningTask(
            rhsm_config_proxy=config_proxy,
            rhsm_configuration=rhsm_config
        )
        task.run()
        # check the RHSM config proxy was called correctly
        config_proxy.SetAll.assert_called_once_with({"foo": get_variant(Str, "bar")}, "")

    @patch("pyanaconda.modules.subscription.satellite.run_satellite_provisioning_script")
    def test_provision_target_no_op(self, run_script_function):
        """Test the ProvisionTargetSystemForSatelliteTask - no op."""
        # create the task and run it
        task = ProvisionTargetSystemForSatelliteTask(provisioning_script=None)
        task.run()
        # make sure we did not try to provision the system with
        # registered_to_satellite == False
        run_script_function.assert_not_called()

    @patch("pyanaconda.modules.subscription.satellite.run_satellite_provisioning_script")
    def test_provision_target_success(self, run_script_function):
        """Test the ProvisionTargetSystemForSatelliteTask - success."""
        # make the run script function return True, indicating success
        run_script_function.return_value = True
        # create the task and run it
        task = ProvisionTargetSystemForSatelliteTask(provisioning_script="foo")
        task.run()
        # make sure we did try to provision the system with
        run_script_function.assert_called_once_with(
            provisioning_script="foo",
            run_on_target_system=True
        )

    @patch("pyanaconda.modules.subscription.satellite.run_satellite_provisioning_script")
    def test_provision_target_failure(self, run_script_function):
        """Test the ProvisionTargetSystemForSatelliteTask - failure."""
        # make the run script function return False, indicating failure
        run_script_function.return_value = False
        # create the task and run it
        task = ProvisionTargetSystemForSatelliteTask(provisioning_script="foo")
        # check if the correct exception for a failure is raised
        with pytest.raises(SatelliteProvisioningError):
            task.run()
        # make sure we did try to provision the system with
        run_script_function.assert_called_once_with(
            provisioning_script="foo",
            run_on_target_system=True
        )


class RegisterAndSubscribeTestCase(unittest.TestCase):
    """Test the RegisterAndSubscribeTask orchestration task.

    This task does orchestration of many individual tasks,
    so it makes sense to have a separate test case for it.
    """

    def test_get_proxy_url(self):
        """Test proxy URL generation in RegisterAndSubscribeTask."""
        # no proxy data provided
        empty_request = SubscriptionRequest()
        assert RegisterAndSubscribeTask._get_proxy_url(empty_request) is None
        # proxy data provided in subscription request
        request_with_proxy_data = SubscriptionRequest()
        request_with_proxy_data.server_proxy_hostname = "proxy.example.com"
        request_with_proxy_data.server_proxy_user = "foo_user"
        request_with_proxy_data.server_proxy_password.set_secret("foo_password")
        request_with_proxy_data.server_proxy_port = 1234
        assert RegisterAndSubscribeTask._get_proxy_url(request_with_proxy_data) == \
            "http://foo_user:foo_password@proxy.example.com:1234"
        # one more time without valid port set
        request_with_proxy_data = SubscriptionRequest()
        request_with_proxy_data.server_proxy_hostname = "proxy.example.com"
        request_with_proxy_data.server_proxy_user = "foo_user"
        request_with_proxy_data.server_proxy_password.set_secret("foo_password")
        request_with_proxy_data.server_proxy_port = -1
        # this should result in the default proxy port 3128 being used
        assert RegisterAndSubscribeTask._get_proxy_url(request_with_proxy_data) == \
            "http://foo_user:foo_password@proxy.example.com:3128"

    def test_registration_data_json_parsing(self):
        """Test the registration data JSON parsing method of RegisterAndSubscribeTask."""
        parse_method = RegisterAndSubscribeTask._detect_sca_from_registration_data
        # the parsing method should be able to survive also getting an empty string
        # or even None, returning False
        assert not parse_method("")
        assert not parse_method(None)

        # registration data without owner key
        no_owner_data = {
            "foo": "123",
            "bar": "456",
            "baz": "789"
        }
        assert not parse_method(json.dumps(no_owner_data))

        # registration data with owner key but without the necessary
        # contentAccessMode key
        no_access_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner"
            },
            "bar": "456",
            "baz": "789"
        }
        assert not parse_method(json.dumps(no_access_mode_data))

        # registration data with owner key but without the necessary
        # contentAccessMode key
        no_access_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner"
            },
            "bar": "456",
            "baz": "789"
        }
        assert not parse_method(json.dumps(no_access_mode_data))

        # registration data for SCA mode
        sca_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "org_environment"
            },
            "bar": "456",
            "baz": "789"
        }
        assert parse_method(json.dumps(sca_mode_data))

        # registration data for entitlement mode
        entitlement_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "entitlement"
            },
            "bar": "456",
            "baz": "789"
        }
        assert not parse_method(json.dumps(entitlement_mode_data))

        # registration data for unknown mode
        unknown_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "something_else"
            },
            "bar": "456",
            "baz": "789"
        }
        assert not parse_method(json.dumps(unknown_mode_data))

    @patch("pyanaconda.modules.subscription.runtime.DownloadSatelliteProvisioningScriptTask")
    def test_provision_system_for_satellite_skip(self, download_task):
        """Test Satellite provisioning in RegisterAndSubscribeTask - skip."""
        # create the task and related bits
        subscription_request = SubscriptionRequest()
        subscription_request.server_hostname = \
            SERVER_HOSTNAME_NOT_SATELLITE_PREFIX + "something.else.example.com"
        task = RegisterAndSubscribeTask(
            rhsm_observer=Mock(),
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # run the provisioning method
        task._provision_system_for_satellite()
        # detect if provisioning is skipped by checking if the
        # DownloadSatelliteProvisioningScriptTask has been instantiated
        download_task.assert_not_called()

    @patch("pyanaconda.modules.subscription.runtime.DownloadSatelliteProvisioningScriptTask")
    def test_provision_system_for_satellite_download_error(self, download_task):
        """Test Satellite provisioning in RegisterAndSubscribeTask - script download error."""
        # create the task and related bits
        subscription_request = SubscriptionRequest()
        subscription_request.server_hostname = "satellite.example.com"
        satellite_script_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=Mock(),
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=satellite_script_callback,
            config_backup_callback=Mock()
        )
        # make the mock download task fail
        download_task.side_effect = SatelliteProvisioningError()
        # run the provisioning method, check correct exception is raised
        with pytest.raises(SatelliteProvisioningError):
            task._provision_system_for_satellite()
        # download task should have been instantiated
        download_task.assert_called_once_with(
            satellite_url='satellite.example.com',
            proxy_url=None)
        # but the callback should not have been called due to the failure
        satellite_script_callback.assert_not_called()

    @patch("pyanaconda.core.service.restart_service")
    @patch("pyanaconda.modules.subscription.runtime.RunSatelliteProvisioningScriptTask")
    @patch("pyanaconda.modules.subscription.runtime.DownloadSatelliteProvisioningScriptTask")
    @patch("pyanaconda.modules.subscription.runtime.BackupRHSMConfBeforeSatelliteProvisioningTask")
    def test_provision_satellite_run_error(self, backup_task, download_task, run_script_task,
                                           restart_service):
        """Test Satellite provisioning in RegisterAndSubscribeTask - script run failed."""
        # create the task and related bits
        subscription_request = SubscriptionRequest()
        subscription_request.server_hostname = "satellite.example.com"
        satellite_script_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=Mock(),
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=satellite_script_callback,
            config_backup_callback=Mock()
        )
        # make the mock download task return the script from its run() method
        download_task.return_value.run.return_value = "foo bar script"
        # make the mock run task fail
        run_script_task.side_effect = SatelliteProvisioningError()
        # make the mock backup task return mock RHSM config dict
        backup_task.return_value.run.return_value = {"foo": {"bar": "baz"}}
        # run the provisioning method, check correct exception is raised
        with pytest.raises(SatelliteProvisioningError):
            task._provision_system_for_satellite()
        # download task should have been instantiated
        download_task.assert_called_once_with(
            satellite_url='satellite.example.com',
            proxy_url=None)
        # download callback should have been called
        satellite_script_callback.assert_called_once()
        # then the run script task should have been instantiated
        run_script_task.assert_called_once_with(provisioning_script="foo bar script")
        # but the next call to restart_service should not happen
        # due to the exception being raised
        restart_service.assert_not_called()

    @patch("pyanaconda.core.service.restart_service")
    @patch("pyanaconda.modules.subscription.runtime.RunSatelliteProvisioningScriptTask")
    @patch("pyanaconda.modules.subscription.runtime.BackupRHSMConfBeforeSatelliteProvisioningTask")
    @patch("pyanaconda.modules.subscription.runtime.DownloadSatelliteProvisioningScriptTask")
    def test_provision_success(self, download_task, backup_task, run_script_task, restart_service):
        """Test Satellite provisioning in RegisterAndSubscribeTask - success."""
        # this tests a simulated successful end-to-end provisioning run, which contains
        # some more bits that have been skipped in the previous tests for complexity:
        # - check proxy URL propagates correctly
        # - check the backup task (run between download and run tasks) is run correctly

        # create the task and related bits
        rhsm_observer = Mock()
        subscription_request = SubscriptionRequest()
        subscription_request.server_hostname = "satellite.example.com"
        subscription_request.server_proxy_hostname = "proxy.example.com"
        subscription_request.server_proxy_user = "foo_user"
        subscription_request.server_proxy_password.set_secret("foo_password")
        subscription_request.server_proxy_port = 1234
        config_backup_callback = Mock()
        satellite_script_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=satellite_script_callback,
            config_backup_callback=config_backup_callback
        )
        # mock the roll back method
        task._roll_back_satellite_provisioning = Mock()
        # make the mock download task return the script from its run() method
        download_task.return_value.run.return_value = "foo bar script"
        # make the mock backup task return mock RHSM config dict
        backup_task.return_value.run.return_value = {"foo": {"bar": "baz"}}
        # run the provisioning method
        task._provision_system_for_satellite()
        # download task should have been instantiated
        download_task.assert_called_once_with(
            satellite_url='satellite.example.com',
            proxy_url='http://foo_user:foo_password@proxy.example.com:1234')
        # download callback should have been called
        satellite_script_callback.assert_called_once()
        # next we should attempt to backup RHSM configuration, so that
        # unregistration can correctly cleanup after a Satellite
        # registration attempt
        rhsm_observer.get_proxy.assert_called_once_with(RHSM_CONFIG)
        backup_task.assert_called_once_with(rhsm_config_proxy=rhsm_observer.get_proxy.return_value)
        config_backup_callback.assert_called_once_with({"foo.bar": "baz"})
        # then the run script task should have been instantiated
        run_script_task.assert_called_once_with(provisioning_script="foo bar script")
        # then the RHSM service restart should happen
        restart_service.assert_called_once_with(RHSM_SERVICE_NAME)
        # make sure the rollback method was not called
        task._roll_back_satellite_provisioning.assert_not_called()

    @patch("pyanaconda.modules.subscription.runtime.RegisterWithUsernamePasswordTask")
    def test_registration_error_username_password(self, register_username_task):
        """Test RegisterAndSubscribeTask - username + password registration error."""
        # create the task and related bits
        rhsm_observer = Mock()
        subscription_request = SubscriptionRequest()
        subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD
        subscription_request.account_username = "foo_user"
        subscription_request.account_password.set_secret("foo_password")
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # make the register task throw an exception
        register_username_task.return_value.run_with_signals.side_effect = RegistrationError()
        # check the exception is raised as expected
        with pytest.raises(RegistrationError):
            task.run()
        # check the register task was properly instantiated
        register_username_task.assert_called_once_with(
            rhsm_register_server_proxy=rhsm_observer.get_proxy.return_value,
            username='foo_user',
            password='foo_password',
            organization=''
        )
        # check the register task has been run
        register_username_task.return_value.run_with_signals.assert_called_once()

    @patch("pyanaconda.modules.subscription.runtime.RegisterWithOrganizationKeyTask")
    def test_registration_error_org_key(self, register_org_task):
        """Test RegisterAndSubscribeTask - org + key registration error."""
        # create the task and related bits
        rhsm_observer = Mock()
        subscription_request = SubscriptionRequest()
        subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        subscription_request.organization = "foo_org"
        subscription_request.activation_keys.set_secret(["key1", "key2", "key3"])
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=Mock(),
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=Mock(),
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # make the register task throw an exception
        register_org_task.return_value.run_with_signals.side_effect = RegistrationError()
        # check the exception is raised as expected
        with pytest.raises(RegistrationError):
            task.run()
        # check the register task was properly instantiated
        register_org_task.assert_called_once_with(
            rhsm_register_server_proxy=rhsm_observer.get_proxy.return_value,
            organization='foo_org',
            activation_keys=['key1', 'key2', 'key3']
        )
        # check the register task has been run
        register_org_task.return_value.run_with_signals.assert_called_once()

    @patch("pyanaconda.modules.subscription.runtime.ParseSubscriptionDataTask")
    @patch("pyanaconda.modules.subscription.runtime.RegisterWithOrganizationKeyTask")
    def test_registration_and_subscribe(self, register_task, parse_task):
        """Test RegisterAndSubscribeTask - success."""
        # create the task and related bits
        rhsm_observer = Mock()
        rhsm_register_server = Mock()
        rhsm_syspurpose = Mock()
        rhsm_observer.get_proxy.side_effect = [
            rhsm_register_server, rhsm_syspurpose
        ]
        subscription_request = SubscriptionRequest()
        subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        subscription_request.organization = "foo_org"
        subscription_request.activation_keys.set_secret(["key1", "key2", "key3"])
        system_purpose_data = SystemPurposeData()
        system_purpose_data.sla = "foo_sla"
        subscription_attached_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=system_purpose_data,
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=subscription_attached_callback,
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # mock the Satellite provisioning method
        task._provision_system_for_satellite = Mock()
        # run the main task
        task.run()
        # check satellite provisioning was not attempted
        task._provision_system_for_satellite.assert_not_called()
        # check the register task was properly instantiated and run
        register_task.assert_called_once_with(
            rhsm_register_server_proxy=rhsm_register_server,
            organization='foo_org',
            activation_keys=['key1', 'key2', 'key3']
        )
        register_task.return_value.run_with_signals.assert_called_once()
        # also check the callback was called correctly
        subscription_attached_callback.assert_called_once_with(True)
        # check the subscription parsing task has been properly instantiated and run
        parse_task.assert_called_once_with(
            rhsm_syspurpose_proxy=rhsm_syspurpose
        )
        parse_task.return_value.run_with_signals.assert_called_once()

    @patch("pyanaconda.modules.subscription.runtime.ParseSubscriptionDataTask")
    @patch("pyanaconda.modules.subscription.runtime.RegisterWithOrganizationKeyTask")
    def test_registration_and_subscribe_satellite(self, register_task, parse_task):
        """Test RegisterAndSubscribeTask - success with satellite provisioning."""
        # create the task and related bits
        rhsm_observer = Mock()
        rhsm_register_server = Mock()
        rhsm_syspurpose = Mock()
        rhsm_observer.get_proxy.side_effect = [
            rhsm_register_server, rhsm_syspurpose
        ]
        subscription_request = SubscriptionRequest()
        subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        subscription_request.organization = "foo_org"
        subscription_request.activation_keys.set_secret(["key1", "key2", "key3"])
        subscription_request.server_hostname = "satellite.example.com"
        system_purpose_data = SystemPurposeData()
        system_purpose_data.sla = "foo_sla"
        subscription_attached_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=system_purpose_data,
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=subscription_attached_callback,
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # mock the Satellite provisioning method
        task._provision_system_for_satellite = Mock()
        # run the main task
        task.run()
        # check satellite provisioning was attempted
        task._provision_system_for_satellite.assert_called_once_with()
        # check the register task was properly instantiated and run
        register_task.assert_called_once_with(
            rhsm_register_server_proxy=rhsm_register_server,
            organization='foo_org',
            activation_keys=['key1', 'key2', 'key3']
        )
        register_task.return_value.run_with_signals.assert_called_once()
        # also check the callback was called correctly
        subscription_attached_callback.assert_called_once_with(True)
        # check the subscription parsing task has been properly instantiated and run
        parse_task.assert_called_once_with(
            rhsm_syspurpose_proxy=rhsm_syspurpose
        )
        parse_task.return_value.run_with_signals.assert_called_once()

    @patch("pyanaconda.modules.subscription.runtime.ParseSubscriptionDataTask")
    @patch("pyanaconda.modules.subscription.runtime.RegisterWithOrganizationKeyTask")
    def test_registration_failure_satellite(self, register_task, parse_task):
        """Test RegisterAndSubscribeTask - registration failure with satellite provisioning."""
        # create the task and related bits
        rhsm_observer = Mock()
        rhsm_register_server = Mock()
        rhsm_entitlement = Mock()
        rhsm_syspurpose = Mock()
        rhsm_observer.get_proxy.side_effect = [
            rhsm_register_server, rhsm_entitlement, rhsm_syspurpose
        ]
        subscription_request = SubscriptionRequest()
        subscription_request.type = SUBSCRIPTION_REQUEST_TYPE_ORG_KEY
        subscription_request.organization = "foo_org"
        subscription_request.activation_keys.set_secret(["key1", "key2", "key3"])
        subscription_request.server_hostname = "satellite.example.com"
        system_purpose_data = SystemPurposeData()
        system_purpose_data.sla = "foo_sla"
        subscription_attached_callback = Mock()
        task = RegisterAndSubscribeTask(
            rhsm_observer=rhsm_observer,
            subscription_request=subscription_request,
            system_purpose_data=system_purpose_data,
            registered_callback=Mock(),
            registered_to_satellite_callback=Mock(),
            simple_content_access_callback=Mock(),
            subscription_attached_callback=subscription_attached_callback,
            subscription_data_callback=Mock(),
            satellite_script_callback=Mock(),
            config_backup_callback=Mock()
        )
        # mock the Satellite provisioning method
        task._provision_system_for_satellite = Mock()
        # mock the Satellite rollback method
        task._roll_back_satellite_provisioning = Mock()
        # make the register task throw an exception
        register_task.return_value.run_with_signals.side_effect = RegistrationError()
        # run the main task, epxect registration error
        with pytest.raises(RegistrationError):
            task.run()
        # check satellite provisioning was attempted
        task._provision_system_for_satellite.assert_called_once_with()
        # check the register task was properly instantiated and run
        register_task.assert_called_once_with(
            rhsm_register_server_proxy=rhsm_register_server,
            organization='foo_org',
            activation_keys=['key1', 'key2', 'key3']
        )
        register_task.return_value.run_with_signals.assert_called_once()
        # also check the callback was not called
        subscription_attached_callback.assert_not_called()
        # check the subscription parsing task has not been instantiated and run
        parse_task.assert_not_called()
        parse_task.return_value.run_with_signals.assert_not_called()
        # the Satellite provisioning rollback should have been called due to the failure
        task._roll_back_satellite_provisioning.assert_called_once()


class RetrieveOrganizationsTaskTestCase(unittest.TestCase):
    """Test the organization data parsing task."""

    def test_org_data_json_parsing(self):
        """Test the organization data JSON parsing method of RetrieveOrganizationsTask."""
        parse_method = RetrieveOrganizationsTask._parse_org_data_json
        # the parsing method should be able to survive also getting an empty string,
        # resulting in an empty list being returned
        struct = get_native(
            OrganizationData.to_structure_list(parse_method(""))
        )
        assert struct == []

        # try data with single organization
        single_org_data = [
            {
                "key": "123abc",
                "displayName": "Foo Org",
                "contentAccessMode": "entitlement"
            }
        ]
        single_org_data_json = json.dumps(single_org_data)
        expected_struct_list = [
            {
                "id": "123abc",
                "name": "Foo Org",
            }
        ]

        struct = get_native(
            OrganizationData.to_structure_list(parse_method(single_org_data_json))
        )
        assert struct == expected_struct_list

        # try multiple organizations:
        # - one in entitlement (classic) mode
        # - one in Simple Content Access mode
        # - one in unknown unexpected mode (should fall back to entitlement/classic mode)
        multiple_org_data = [
            {
                "key": "123a",
                "displayName": "Foo Org",
                "contentAccessMode": "entitlement"
            },
            {
                "key": "123b",
                "displayName": "Bar Org",
                "contentAccessMode": "org_environment"
            },
            {
                "key": "123c",
                "displayName": "Baz Org",
                "contentAccessMode": "something_else"
            }
        ]
        multiple_org_data_json = json.dumps(multiple_org_data)
        expected_struct_list = [
            {
                "id": "123a",
                "name": "Foo Org",
            },
            {
                "id": "123b",
                "name": "Bar Org",
            },
            {
                "id": "123c",
                "name": "Baz Org",
            }
        ]
        structs = get_native(
            OrganizationData.to_structure_list(parse_method(multiple_org_data_json))
        )
        assert structs == expected_struct_list

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_get_org_data(self, private_bus, environ_get):
        """Test the RetrieveOrganizationsTask."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # mock the GetOrgs JSON output
        multiple_org_data = [
            {
                "key": "123a",
                "displayName": "Foo Org",
                "contentAccessMode": "entitlement"
            },
            {
                "key": "123b",
                "displayName": "Bar Org",
                "contentAccessMode": "org_environment"
            },
            {
                "key": "123c",
                "displayName": "Baz Org",
                "contentAccessMode": "something_else"
            }
        ]
        multiple_org_data_json = json.dumps(multiple_org_data)
        private_register_proxy.GetOrgs.return_value = multiple_org_data_json

        # instantiate the task and run it
        task = RetrieveOrganizationsTask(rhsm_register_server_proxy=register_server_proxy,
                                         username="foo_user",
                                         password="bar_password")
        org_data_structs = task.run()
        # check the structs based on the JSON data look as expected
        expected_struct_list = [
            {
                "id": "123a",
                "name": "Foo Org",
            },
            {
                "id": "123b",
                "name": "Bar Org",
            },
            {
                "id": "123c",
                "name": "Baz Org",
            }
        ]
        structs = get_native(
            OrganizationData.to_structure_list(org_data_structs)
        )
        assert structs == expected_struct_list

        # check the private register proxy Register method was called correctly
        private_register_proxy.GetOrgs.assert_called_once_with("foo_user",
                                                               "bar_password",
                                                               {},
                                                               "en_US.UTF-8")

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_get_org_data_cached(self, private_bus, environ_get):
        """Test the RetrieveOrganizationsTask - return cached data on error."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # simulate GetOrgs call failure
        private_register_proxy.GetOrgs.side_effect = DBusError("org listing failed")
        # create some dummy cached data
        cached_structs_list = [
            {
                "id": get_variant(Str, "123a cached"),
                "name": get_variant(Str, "Foo Org cached"),
            },
            {
                "id": get_variant(Str, "123b cached"),
                "name": get_variant(Str, "Bar Org cached"),
            },
            {
                "id": get_variant(Str, "123c cached"),
                "name": get_variant(Str, "Baz Org cached"),
            }
        ]
        cached_structs = OrganizationData.from_structure_list(cached_structs_list)
        RetrieveOrganizationsTask._org_data_list_cache = cached_structs

        # instantiate the task and run it with cached data
        task = RetrieveOrganizationsTask(rhsm_register_server_proxy=register_server_proxy,
                                         username="foo_user",
                                         password="bar_password")
        org_data_structs = task.run()
        # check the returned structs are based on the cache data, not the
        # JSON data the mock-API would return
        expected_struct_list = [
            {
                "id": "123a cached",
                "name": "Foo Org cached",
            },
            {
                "id": "123b cached",
                "name": "Bar Org cached",
            },
            {
                "id": "123c cached",
                "name": "Baz Org cached",
            }
        ]
        structs = get_native(
            OrganizationData.to_structure_list(org_data_structs)
        )
        assert structs == expected_struct_list

        # check the private register proxy Register method was *not* called
        # as all data should come from the cache, if provided, with *no*
        # DBus API access
        private_register_proxy.GetOrgs.assert_called_once_with(
            'foo_user', 'bar_password', {}, 'en_US.UTF-8'
        )

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_get_org_data_ignore_cache(self, private_bus, environ_get):
        """Test the RetrieveOrganizationsTask - do not use cache on success."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # mock the GetOrgs JSON output
        multiple_org_data = [
            {
                "key": "123a",
                "displayName": "Foo Org",
                "contentAccessMode": "entitlement"
            },
            {
                "key": "123b",
                "displayName": "Bar Org",
                "contentAccessMode": "org_environment"
            },
            {
                "key": "123c",
                "displayName": "Baz Org",
                "contentAccessMode": "something_else"
            }
        ]
        multiple_org_data_json = json.dumps(multiple_org_data)
        private_register_proxy.GetOrgs.return_value = multiple_org_data_json
        # create some dummy cached data
        cached_structs_list = [
            {
                "id": get_variant(Str, "123a cached"),
                "name": get_variant(Str, "Foo Org cached"),
            },
            {
                "id": get_variant(Str, "123b cached"),
                "name": get_variant(Str, "Bar Org cached"),
            },
            {
                "id": get_variant(Str, "123c cached"),
                "name": get_variant(Str, "Baz Org cached"),
            }
        ]
        cached_structs = OrganizationData.from_structure_list(cached_structs_list)
        RetrieveOrganizationsTask._org_data_list_cache = cached_structs

        # instantiate the task and run it with cached data
        task = RetrieveOrganizationsTask(rhsm_register_server_proxy=register_server_proxy,
                                         username="foo_user",
                                         password="bar_password")
        org_data_structs = task.run()

        # check the structs based on the GetOrgs returned JSON data look as expected
        expected_struct_list = [
            {
                "id": "123a",
                "name": "Foo Org",
            },
            {
                "id": "123b",
                "name": "Bar Org",
            },
            {
                "id": "123c",
                "name": "Baz Org",
            }
        ]
        structs = get_native(
            OrganizationData.to_structure_list(org_data_structs)
        )
        assert structs == expected_struct_list

        # check the private register proxy Register method was *not* called
        # as all data should come from the cache, if provided, with *no*
        # DBus API access
        private_register_proxy.GetOrgs.assert_called_once_with(
            'foo_user', 'bar_password', {}, 'en_US.UTF-8'
        )

    @patch("os.environ.get", return_value="en_US.UTF-8")
    @patch("pyanaconda.modules.subscription.runtime.RHSMPrivateBus")
    def test_get_org_data_cache_reset(self, private_bus, environ_get):
        """Test the RetrieveOrganizationsTask - test cache reset."""
        # register server proxy
        register_server_proxy = Mock()
        # private register proxy
        get_proxy = private_bus.return_value.__enter__.return_value.get_proxy
        private_register_proxy = get_proxy.return_value
        # simulate GetOrgs call failure
        private_register_proxy.GetOrgs.side_effect = DBusError("org listing failed")
        # create some dummy cached data
        cached_structs_list = [
            {
                "id": get_variant(Str, "123a cached"),
                "name": get_variant(Str, "Foo Org cached"),
            },
            {
                "id": get_variant(Str, "123b cached"),
                "name": get_variant(Str, "Bar Org cached"),
            },
            {
                "id": get_variant(Str, "123c cached"),
                "name": get_variant(Str, "Baz Org cached"),
            }
        ]
        cached_structs = OrganizationData.from_structure_list(cached_structs_list)
        RetrieveOrganizationsTask._org_data_list_cache = cached_structs

        # instantiate the task and run it with cached data
        task = RetrieveOrganizationsTask(rhsm_register_server_proxy=register_server_proxy,
                                         username="foo_user",
                                         password="bar_password",
                                         reset_cache=True)
        org_data_structs = task.run()
        # we dropped the cache and the GetOrgs() call failed, so we return the
        # contents of the empty cache
        expected_struct_list = []
        structs = get_native(
            OrganizationData.to_structure_list(org_data_structs)
        )
        assert structs == expected_struct_list

        # check the private register proxy Register method was *not* called
        # as all data should come from the cache, if provided, with *no*
        # DBus API access
        private_register_proxy.GetOrgs.assert_called_once_with(
            'foo_user', 'bar_password', {}, 'en_US.UTF-8'
        )
