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
import pytest
import json

from unittest.mock import patch, Mock, call

import tempfile

from dasbus.typing import get_variant, get_native, Str
from dasbus.error import DBusError

from pyanaconda.core.path import join_paths
from pyanaconda.core.constants import SUBSCRIPTION_REQUEST_TYPE_ORG_KEY, \
    RHSM_SYSPURPOSE_FILE_PATH

from pyanaconda.modules.common.errors.installation import InsightsConnectError, \
    InsightsClientMissingError, SubscriptionTokenTransferError
from pyanaconda.modules.common.errors.subscription import RegistrationError, \
    SubscriptionError
from pyanaconda.modules.common.structures.subscription import SystemPurposeData, \
    SubscriptionRequest, AttachedSubscription
from pyanaconda.modules.common.constants.services import RHSM
from pyanaconda.modules.common.constants.objects import RHSM_REGISTER

from pyanaconda.modules.subscription.installation import ConnectToInsightsTask, \
    RestoreRHSMDefaultsTask, TransferSubscriptionTokensTask

from pyanaconda.modules.subscription.runtime import SetRHSMConfigurationTask, \
    RHSMPrivateBus, RegisterWithUsernamePasswordTask, RegisterWithOrganizationKeyTask, \
    UnregisterTask, AttachSubscriptionTask, SystemPurposeConfigurationTask, \
    ParseAttachedSubscriptionsTask

import gi
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
        # instantiate the task and run it
        task = RegisterWithUsernamePasswordTask(rhsm_register_server_proxy=register_server_proxy,
                                                username="foo_user",
                                                password="bar_password")
        task.run()
        # check the private register proxy Register method was called correctly
        private_register_proxy.Register.assert_called_once_with("",
                                                                "foo_user",
                                                                "bar_password",
                                                                {},
                                                                {},
                                                                "en_US.UTF-8")

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
                                                password="bar_password")
        with pytest.raises(RegistrationError):
            task.run()
        # check private register proxy Register method was called correctly
        private_register_proxy.Register.assert_called_with("",
                                                           "foo_user",
                                                           "bar_password",
                                                           {},
                                                           {},
                                                           "en_US.UTF-8")

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
        # instantiate the task and run it
        task = RegisterWithOrganizationKeyTask(rhsm_register_server_proxy=register_server_proxy,
                                               organization="123456789",
                                               activation_keys=["foo", "bar", "baz"])
        task.run()
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

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_success(self, environ_get):
        """Test the UnregisterTask - success."""
        # register server proxy
        rhsm_unregister_proxy = Mock()
        # instantiate the task and run it
        task = UnregisterTask(rhsm_unregister_proxy=rhsm_unregister_proxy)
        task.run()
        # check the unregister proxy Unregister method was called correctly
        rhsm_unregister_proxy.Unregister.assert_called_once_with({}, "en_US.UTF-8")

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_unregister_failure(self, environ_get):
        """Test the UnregisterTask - failure."""
        # register server proxy
        rhsm_unregister_proxy = Mock()
        # raise DBusError with error message in JSON
        json_error = '{"message": "Unregistration failed."}'
        rhsm_unregister_proxy.Unregister.side_effect = DBusError(json_error)
        # instantiate the task and run it
        task = UnregisterTask(rhsm_unregister_proxy=rhsm_unregister_proxy)
        with pytest.raises(DBusError):
            task.run()
        # check the unregister proxy Unregister method was called correctly
        rhsm_unregister_proxy.Unregister.assert_called_once_with({}, "en_US.UTF-8")


class AttachSubscriptionTaskTestCase(unittest.TestCase):
    """Test the subscription task."""

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_attach_subscription_task_success(self, environ_get):
        """Test the AttachSubscriptionTask - success."""
        rhsm_attach_proxy = Mock()
        task = AttachSubscriptionTask(rhsm_attach_proxy=rhsm_attach_proxy,
                                      sla="foo_sla")
        task.run()
        rhsm_attach_proxy.AutoAttach.assert_called_once_with("foo_sla",
                                                             {},
                                                             "en_US.UTF-8")

    @patch("os.environ.get", return_value="en_US.UTF-8")
    def test_attach_subscription_task_failure(self, environ_get):
        """Test the AttachSubscriptionTask - failure."""
        rhsm_attach_proxy = Mock()
        # raise DBusError with error message in JSON
        json_error = '{"message": "Failed to attach subscription."}'
        rhsm_attach_proxy.AutoAttach.side_effect = DBusError(json_error)
        task = AttachSubscriptionTask(rhsm_attach_proxy=rhsm_attach_proxy,
                                      sla="foo_sla")
        with pytest.raises(SubscriptionError):
            task.run()
        rhsm_attach_proxy.AutoAttach.assert_called_once_with("foo_sla",
                                                             {},
                                                             "en_US.UTF-8")


class ParseAttachedSubscriptionsTaskTestCase(unittest.TestCase):
    """Test the attached subscription parsing task."""

    def test_pretty_date(self):
        """Test the pretty date method of ParseAttachedSubscriptionsTask."""
        pretty_date_method = ParseAttachedSubscriptionsTask._pretty_date
        # try to parse ISO 8601 first
        assert pretty_date_method("2015-12-22") == "Dec 22, 2015"
        # the method expects short mm/dd/yy dates
        assert pretty_date_method("12/22/15") == "Dec 22, 2015"
        # returns the input if parsing fails
        ambiguous_date = "noon of the twenty first century"
        assert pretty_date_method(ambiguous_date) == ambiguous_date

    def test_subscription_json_parsing(self):
        """Test the subscription JSON parsing method of ParseAttachedSubscriptionsTask."""
        parse_method = ParseAttachedSubscriptionsTask._parse_subscription_json
        # the method should be able to survive the RHSM DBus API returning an empty string,
        # as empty list of subscriptions is a lesser issue than crashed installation
        assert parse_method("") == []
        # try parsing a json file containing two subscriptions
        # - to make this look sane, we write it as a dict that we then convert to JSON
        subscription_dict = {
            "consumed": [
                {
                    "subscription_name": "Foo Bar Beta",
                    "service_level": "very good",
                    "sku": "ABC1234",
                    "contract": "12345678",
                    "starts": "05/12/20",
                    "ends": "05/12/21",
                    "quantity_used": "1"
                },
                {
                    "subscription_name": "Foo Bar Beta NG",
                    "service_level": "even better",
                    "sku": "ABC4321",
                    "contract": "87654321",
                    "starts": "now",
                    "ends": "never",
                    "quantity_used": "1000"
                },
                {
                    "subscription_name": "Foo Bar Beta NG",
                    "service_level": "much wow",
                    "sku": "ABC5678",
                    "contract": "12344321",
                    "starts": "2020-05-12",
                    "ends": "never",
                    "quantity_used": "1000"
                }
            ]

        }
        subscription_json = json.dumps(subscription_dict)
        expected_structs = [
            {
                "name": "Foo Bar Beta",
                "service-level": "very good",
                "sku": "ABC1234",
                "contract": "12345678",
                "start-date": "May 12, 2020",
                "end-date": "May 12, 2021",
                "consumed-entitlement-count": 1
            },
            {
                "name": "Foo Bar Beta NG",
                "service-level": "even better",
                "sku": "ABC4321",
                "contract": "87654321",
                "start-date": "now",
                "end-date": "never",
                "consumed-entitlement-count": 1000
            },
            {
                "name": "Foo Bar Beta NG",
                "service-level": "much wow",
                "sku": "ABC5678",
                "contract": "12344321",
                "start-date": "May 12, 2020",
                "end-date": "never",
                "consumed-entitlement-count": 1000
            }
        ]
        structs = get_native(
            AttachedSubscription.to_structure_list(parse_method(subscription_json))
        )
        # check the content of the AttachedSubscription corresponds to the input JSON,
        # including date formatting
        assert structs == expected_structs

    def test_system_purpose_json_parsing(self):
        """Test the system purpose JSON parsing method of ParseAttachedSubscriptionsTask."""
        parse_method = ParseAttachedSubscriptionsTask._parse_system_purpose_json
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
        """Test the ParseAttachedSubscriptionsTask."""
        # prepare mock proxies the task is expected to interact with
        rhsm_entitlement_proxy = Mock()
        rhsm_entitlement_proxy.GetPools.return_value = "foo"
        rhsm_syspurpose_proxy = Mock()
        rhsm_syspurpose_proxy.GetSyspurpose.return_value = "bar"
        task = ParseAttachedSubscriptionsTask(rhsm_entitlement_proxy=rhsm_entitlement_proxy,
                                              rhsm_syspurpose_proxy=rhsm_syspurpose_proxy)
        # mock the parsing methods
        subscription1 = AttachedSubscription()
        subscription2 = AttachedSubscription()
        task._parse_subscription_json = Mock()
        task._parse_subscription_json.return_value = [subscription1, subscription2]
        system_purpose_data = SystemPurposeData()
        task._parse_system_purpose_json = Mock()
        task._parse_system_purpose_json.return_value = system_purpose_data
        # run the task
        result = task.run()
        # check DBus proxies were called as expected
        rhsm_entitlement_proxy.GetPools.assert_called_once_with({'pool_subsets':
                                                                get_variant(Str, "consumed")},
                                                                {},
                                                                "en_US.UTF-8")
        rhsm_syspurpose_proxy.GetSyspurpose.assert_called_once_with("en_US.UTF-8")
        # check the parsing methods were called
        task._parse_subscription_json.assert_called_once_with("foo")
        task._parse_system_purpose_json.assert_called_once_with("bar")
        # check the result that has been returned is as expected
        assert result.attached_subscriptions == [subscription1, subscription2]
        assert result.system_purpose_data == system_purpose_data
