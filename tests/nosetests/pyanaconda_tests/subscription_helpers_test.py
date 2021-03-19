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
import tempfile

import unittest
from unittest.mock import patch, Mock, MagicMock, call

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core import util
from pyanaconda.core.constants import RHSM_SYSPURPOSE_FILE_PATH, \
    THREAD_WAIT_FOR_CONNECTING_NM, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD, \
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY, SOURCE_TYPE_CLOSEST_MIRROR, \
    SOURCE_TYPE_CDN, SOURCE_TYPE_CDROM, PAYLOAD_TYPE_DNF, PAYLOAD_TYPE_RPM_OSTREE, \
    SOURCE_TYPE_URL

from pyanaconda.modules.common.errors.subscription import UnregistrationError, \
    RegistrationError, SubscriptionError
from pyanaconda.modules.common.structures.subscription import SubscriptionRequest, \
    OrganizationData

from pyanaconda.core.subscription import check_system_purpose_set

from pyanaconda.ui.lib.subscription import SubscriptionPhase, \
    register_and_subscribe, unregister, org_keys_sufficient, \
    username_password_sufficient, check_cdn_is_installation_source, \
    check_simple_content_access_is_enabled


class CheckSystemPurposeSetTestCase(unittest.TestCase):
    """Test the check_system_purpose_set helper function."""

    def check_system_purpose_set_test(self):
        """Test the check_system_purpose_set() helper function."""
        # system purpose set
        with tempfile.TemporaryDirectory() as sysroot:
            # create a dummy syspurpose file
            syspurpose_path = RHSM_SYSPURPOSE_FILE_PATH
            directory = os.path.split(syspurpose_path)[0]
            os.makedirs(util.join_paths(sysroot, directory))
            os.mknod(util.join_paths(sysroot, syspurpose_path))
            self.assertTrue(check_system_purpose_set(sysroot))

        # system purpose not set
        with tempfile.TemporaryDirectory() as sysroot:
            self.assertFalse(check_system_purpose_set(sysroot))

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def check_simple_content_access_is_enabled_sca_mode_test(self, get_proxy, run_task):
        """Test the check_simple_content_access_is_enabled() helper function - SCA mode."""
        # mock the module proxy
        subscription_module_proxy = Mock()
        # mock the org fetching DBus task
        org_data_task_proxy = Mock()
        # create some dummy data
        org_data_1 = OrganizationData()
        org_data_1.organization_id = "123b"
        org_data_1.name = "Bar Org"
        org_data_1.simple_content_access_enabled = True
        # encode is as variant
        org_data_task_proxy.GetResult.return_value = get_variant(
            List[Structure], OrganizationData.to_structure_list([org_data_1])
        )
        # export the two proxies via side effects as the get_proxy() method gets called twice
        get_proxy.side_effect = [subscription_module_proxy, org_data_task_proxy]
        # run the function
        self.assertTrue(check_simple_content_access_is_enabled())
        # check we requested the right task
        subscription_module_proxy.ParseOrganizationDataWithTask.assert_called_once()

        # check we tried to run the task
        run_task.assert_called()

        # check we requested task results
        org_data_task_proxy.GetResult.assert_called_once()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def check_simple_content_access_is_enabled_non_sca_mode_test(self, get_proxy, run_task):
        """Test the check_simple_content_access_is_enabled() helper function - non SCA mode."""
        # mock the module proxy
        subscription_module_proxy = Mock()
        # mock the org fetching DBus task
        org_data_task_proxy = Mock()
        # create some dummy data
        org_data_1 = OrganizationData()
        org_data_1.organization_id = "123a"
        org_data_1.name = "Bar Org"
        org_data_1.simple_content_access_enabled = False
        # encode is as variant
        org_data_task_proxy.GetResult.return_value = get_variant(
            List[Structure], OrganizationData.to_structure_list([org_data_1])
        )
        # export the two proxies via side effects as the get_proxy() method gets called twice
        get_proxy.side_effect = [subscription_module_proxy, org_data_task_proxy]
        # run the function
        self.assertFalse(check_simple_content_access_is_enabled())
        # check we requested the right task
        subscription_module_proxy.ParseOrganizationDataWithTask.assert_called_once()

        # check we tried to run the task
        run_task.assert_called()

        # check we requested task results
        org_data_task_proxy.GetResult.assert_called_once()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def check_simple_content_access_is_enabled_multiple_orgs_test(self, get_proxy, run_task):
        """Test the check_simple_content_access_is_enabled() helper function - multiple orgs."""
        # If multiple sets of organization data are returned, we pick the first one in the list.
        # This is do to not fully supporting accounts that exist in multiple organizations.
        # Once proper support for this is introduced, this case should no longer happen as
        # either the account is a member of just one organization or a specific one was picked
        # from a list presented to the user by Anaconda.

        # mock the module proxy
        subscription_module_proxy = Mock()
        # mock the org fetching DBus task
        org_data_task_proxy = Mock()
        # create some dummy data
        org_data_1 = OrganizationData()
        org_data_1.organization_id = "123a"
        org_data_1.name = "Bar Org"
        org_data_1.simple_content_access_enabled = True

        org_data_2 = OrganizationData()
        org_data_2.organization_id = "123b"
        org_data_2.name = "Baz Org"
        org_data_2.simple_content_access_enabled = False

        # encode is as variant
        org_data_task_proxy.GetResult.return_value = get_variant(
            List[Structure], OrganizationData.to_structure_list([org_data_1, org_data_2])
        )
        # export the two proxies via side effects as the get_proxy() method gets called twice
        get_proxy.side_effect = [subscription_module_proxy, org_data_task_proxy]
        # run the function
        self.assertTrue(check_simple_content_access_is_enabled())
        # check we requested the right task
        subscription_module_proxy.ParseOrganizationDataWithTask.assert_called_once()

        # check we tried to run the task
        run_task.assert_called()

        # check we requested task results
        org_data_task_proxy.GetResult.assert_called_once()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def check_simple_content_access_is_enabled_no_org_data_test(self, get_proxy, run_task):
        """Test the check_simple_content_access_is_enabled() helper function - no org data."""
        # This tests a case where GetOrgs() returns no data at all for the given Red Hat account.
        # In such a case we assume SCA is not enabled.

        # mock the module proxy
        subscription_module_proxy = Mock()
        # mock the org fetching DBus task
        org_data_task_proxy = Mock()
        # take an empty list and encode as variant
        org_data_task_proxy.GetResult.return_value = get_variant(
            List[Structure], OrganizationData.to_structure_list([])
        )
        # export the two proxies via side effects as the get_proxy() method gets called twice
        get_proxy.side_effect = [subscription_module_proxy, org_data_task_proxy]
        # run the function
        self.assertFalse(check_simple_content_access_is_enabled())
        # check we requested the right task
        subscription_module_proxy.ParseOrganizationDataWithTask.assert_called_once()

        # check we tried to run the task
        run_task.assert_called()

        # check we requested task results
        org_data_task_proxy.GetResult.assert_called_once()


class AsynchronousRegistrationTestCase(unittest.TestCase):
    """Test the asynchronous registration/unregistration helper functions."""

    PASSWORD_REQUEST = {
        "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
        "organization": get_variant(Str, "123456789"),
        "account-username": get_variant(Str, "foo_user"),
        "server-hostname": get_variant(Str, "candlepin.foo.com"),
        "rhsm-baseurl": get_variant(Str, "cdn.foo.com"),
        "server-proxy-hostname": get_variant(Str, "proxy.foo.com"),
        "server-proxy-port": get_variant(Int, 9001),
        "server-proxy-user": get_variant(Str, "foo_proxy_user"),
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

    PASSWORD_MISSING_REQUEST = {
        "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD),
        "organization": get_variant(Str, "123456789"),
        "account-username": get_variant(Str, "foo_user"),
        "server-hostname": get_variant(Str, "candlepin.foo.com"),
        "rhsm-baseurl": get_variant(Str, "cdn.foo.com"),
        "server-proxy-hostname": get_variant(Str, "proxy.foo.com"),
        "server-proxy-port": get_variant(Int, 9001),
        "server-proxy-user": get_variant(Str, "foo_proxy_user"),
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
                        {"type": get_variant(Str, "HIDDEN"),
                         "value": get_variant(Str, "")})
    }

    KEY_REQUEST = {
        "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY),
        "organization": get_variant(Str, "123456789"),
        "account-username": get_variant(Str, "foo_user"),
        "server-hostname": get_variant(Str, "candlepin.foo.com"),
        "rhsm-baseurl": get_variant(Str, "cdn.foo.com"),
        "server-proxy-hostname": get_variant(Str, "proxy.foo.com"),
        "server-proxy-port": get_variant(Int, 9001),
        "server-proxy-user": get_variant(Str, "foo_proxy_user"),
        "account-password":
            get_variant(Structure,
                        {"type": get_variant(Str, "HIDDEN"),
                         "value": get_variant(Str, "")}),
        "activation-keys":
            get_variant(Structure,
                        {"type": get_variant(Str, "TEXT"),
                         "value": get_variant(List[Str], [])}),
        "server-proxy-password":
            get_variant(Structure,
                        {"type": get_variant(Str, "HIDDEN"),
                         "value": get_variant(Str, "")})
    }

    KEY_MISSING_REQUEST = {
        "type": get_variant(Str, SUBSCRIPTION_REQUEST_TYPE_ORG_KEY),
        "organization": get_variant(Str, "123456789"),
        "account-username": get_variant(Str, "foo_user"),
        "server-hostname": get_variant(Str, "candlepin.foo.com"),
        "rhsm-baseurl": get_variant(Str, "cdn.foo.com"),
        "server-proxy-hostname": get_variant(Str, "proxy.foo.com"),
        "server-proxy-port": get_variant(Int, 9001),
        "server-proxy-user": get_variant(Str, "foo_proxy_user"),
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
                        {"type": get_variant(Str, "HIDDEN"),
                         "value": get_variant(Str, "")})
    }

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def org_keys_sufficient_test(self, get_proxy):
        """Test the org_keys_sufficient() helper method."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function
        self.assertTrue(org_keys_sufficient())

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def org_keys_sufficient_not_sufficient_test(self, get_proxy):
        """Test the org_keys_sufficient() helper method - not sufficient."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_MISSING_REQUEST
        # run the function
        self.assertFalse(org_keys_sufficient())

    def org_keys_sufficient_direct_request_test(self):
        """Test the org_keys_sufficient() helper method - direct request."""
        # run the function with sufficient authentication data
        request = SubscriptionRequest.from_structure(self.KEY_REQUEST)
        self.assertTrue(org_keys_sufficient(subscription_request=request))
        # run the function with insufficient authentication data
        request = SubscriptionRequest.from_structure(self.KEY_MISSING_REQUEST)
        self.assertFalse(org_keys_sufficient(subscription_request=request))


    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def username_password_sufficient_test(self, get_proxy):
        """Test the username_password_sufficient() helper method."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # run the function
        self.assertTrue(username_password_sufficient())

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def username_password_sufficient_not_sufficient_test(self, get_proxy):
        """Test the username_password_sufficient() helper method - not sufficient."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_MISSING_REQUEST
        # run the function
        self.assertFalse(username_password_sufficient())

    def username_password_sufficient_direct_request_test(self):
        """Test the username_password_sufficient() helper method - direct request."""
        # run the function with sufficient authentication data
        request = SubscriptionRequest.from_structure(self.PASSWORD_REQUEST)
        self.assertTrue(username_password_sufficient(subscription_request=request))
        # run the function with insufficient authentication data
        request = SubscriptionRequest.from_structure(self.PASSWORD_MISSING_REQUEST)
        self.assertFalse(username_password_sufficient(subscription_request=request))

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_org_key_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - org & key."""
        payload = Mock()
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CLOSEST_MIRROR
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterOrganizationKeyWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_username_password_test(self, get_proxy, thread_mgr_wait, run_task,
                                        switch_source, check_sca_enabled):
        """Test the register_and_subscribe() helper method - username & password."""
        payload = Mock()
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CLOSEST_MIRROR
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_register_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - registered system."""
        payload = Mock()
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CLOSEST_MIRROR
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        # - this should add additional unregister phase and task
        subscription_proxy.IsRegistered = True
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # check the phases and their order
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        subscription_proxy.RegisterOrganizationKeyWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_task_failed_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - unregistration failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        # - this should add additional unregister phase and task
        subscription_proxy.IsRegistered = True
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # make the first (unregistration) task fail
        run_task.side_effect = [True, UnregistrationError("unregistration failed")]
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # there should be only the unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once_with("unregistration failed")
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_org_key_failed_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - org & key failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # make the first (registration) task fail
        run_task.side_effect = [True, RegistrationError("registration failed")]
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # there should be only the registration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once_with("registration failed")
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterOrganizationKeyWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_key_missing_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - key missing."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_MISSING_REQUEST
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # there should be only the registration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once()
        # in this case we fail before requesting any other task than
        # the config one
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_username_password_task_failed_test(self, get_proxy, thread_mgr_wait,
                                                    run_task, switch_source, check_sca_enabled):
        """Test the register_and_subscribe() helper method - username & password failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # make the first (registration) task fail
        run_task.side_effect = [True, RegistrationError("registration failed")]
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # there should be only the registration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once_with("registration failed")
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_password_missing_test(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - password missing."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_MISSING_REQUEST
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # there should be only the registration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once()
        # in this case we fail before requesting any other task than
        # the config one
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_override_cdrom_test(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                     restart_thread):
        """Test the register_and_subscribe() helper method - override CDROM source."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        payload.data.repo.dataList = MagicMock(return_value=[])
        source_proxy_1 = Mock()
        source_proxy_1.Type = SOURCE_TYPE_CDROM
        source_proxy_2 = Mock()
        source_proxy_2.Type = SOURCE_TYPE_CDN
        payload.get_source_proxy.side_effect = [
            source_proxy_1,
            source_proxy_2
        ]
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=True)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterOrganizationKeyWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # and tried to override the CDROM source, as it is on a list of sources
        # that are appropriate to be overriden by the CDN source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDN)
        # and tried to run them
        run_task.assert_called()
        # tried to restart the payload as CDN is set and we need to restart
        # the payload to make it usable
        restart_thread.assert_called_once()

    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_override_cdrom_no_restart_test(self, get_proxy, thread_mgr_wait, run_task,
                                                switch_source, restart_thread):
        """Test the register_and_subscribe() helper method - override CDROM source, no restart."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        payload.data.repo.dataList = MagicMock(return_value=[])
        source_proxy_1 = Mock()
        source_proxy_1.Type = SOURCE_TYPE_CDROM
        source_proxy_2 = Mock()
        source_proxy_2.Type = SOURCE_TYPE_CDN
        payload.get_source_proxy.side_effect = [
            source_proxy_1,
            source_proxy_2
        ]
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function & tell it not to restart payload
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=False)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterOrganizationKeyWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # and tried to override the CDROM source, as it is on a list of sources
        # that are appropriate to be overriden by the CDN source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDN)
        # and tried to run them
        run_task.assert_called()
        # we told the payload not to restart
        restart_thread.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def subscription_task_failed_test(self, get_proxy, thread_mgr_wait, run_task,
                                      switch_source, check_sca_enabled):
        """Test the register_and_subscribe() helper method - failed to attach subscription."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # make the second (subscription) task fail
        run_task.side_effect = [True, True, SubscriptionError("failed to attach subscription")]
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # there should be only the registration & subscription phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once_with("failed to attach subscription")
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_test(self, get_proxy, run_task):
        """Test the unregister() helper method."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=None,
                   progress_callback=progress_callback,
                   error_callback=error_callback)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_not_registered_test(self, get_proxy, run_task):
        """Test the unregister() helper method - not registered."""
        # this is effectively a no-op
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = False
        # run the function
        unregister(payload=payload,
                   overridden_source_type=None,
                   progress_callback=progress_callback,
                   error_callback=error_callback)
        # there should be just the done phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # no need to request and run any tasks
        run_task.assert_not_called()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_failed_test(self, get_proxy, run_task):
        """Test the unregister() helper method - unregistration failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # make the unregistration task fail
        run_task.side_effect = [True, UnregistrationError("unregistration failed")]
        # run the function
        unregister(payload=payload,
                   overridden_source_type=None,
                   progress_callback=progress_callback,
                   error_callback=error_callback)
        # there should be only the unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER)]
        )
        # and the error callback should have been triggered
        error_callback.assert_called_once_with("unregistration failed")
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_back_to_cdrom_test(self, get_proxy, run_task, switch_source):
        """Test the unregister() helper method - roll back to CDROM source."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy_1 = Mock()
        source_proxy_1.Type = SOURCE_TYPE_CDN
        source_proxy_2 = Mock()
        source_proxy_2.Type = SOURCE_TYPE_CDROM
        payload.get_source_proxy.side_effect = [
            source_proxy_1,
            source_proxy_2
        ]
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=SOURCE_TYPE_CDROM,
                   progress_callback=progress_callback,
                   error_callback=error_callback)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # also we should have tried switching back to the CDROM source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDROM)

    def check_cdn_is_installation_source_test(self):
        """Test the check_cdn_is_installation_source function."""
        # check CDN is reported as used
        dnf_payload = Mock()
        dnf_payload.type = PAYLOAD_TYPE_DNF
        source_proxy = dnf_payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        self.assertTrue(check_cdn_is_installation_source(dnf_payload))
        # check CDN is not reported as used
        dnf_payload = Mock()
        dnf_payload.type = PAYLOAD_TYPE_DNF
        source_proxy = dnf_payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDROM
        self.assertFalse(check_cdn_is_installation_source(dnf_payload))
        # check an unsupported (non DNF) source is handled correctly
        ostree_payload = Mock()
        ostree_payload.type = PAYLOAD_TYPE_RPM_OSTREE
        self.assertFalse(check_cdn_is_installation_source(ostree_payload))

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unsupported_payload_reg_test(self, get_proxy, thread_mgr_wait, run_task,
                                     switch_source, check_sca_enabled):
        """Test registration handles unsupported payload."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_RPM_OSTREE
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unsupported_payload_unregister_test(self, get_proxy, run_task, switch_source):
        """Test that unregister() survives unsupported payload."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_RPM_OSTREE
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=SOURCE_TYPE_CDROM,
                   progress_callback=progress_callback,
                   error_callback=error_callback)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # but we should have not tried to switch source as this
        # payload is not supported
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_payload_restart_test(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                      restart_thread, check_sca_enabled):
        """Test payload restart at registration."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=True)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # tried to restart the payload as CDN is set and we need to restart
        # the payload to make it usable
        restart_thread.assert_called_once()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_payload_no_restart_test(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                         restart_thread, check_sca_enabled):
        """Test payload no restart at registration if not requested."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=False)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # told the helper method not to restart
        restart_thread.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_no_payload_restart_test(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                         restart_thread, check_sca_enabled):
        """Test there is no payload restart during registration for non CDN source."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_URL
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate SCA not enabled
        check_sca_enabled.return_value = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=True)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.ATTACH_SUBSCRIPTION),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.AttachSubscriptionWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()
        # Payload should have not been restarted as URL is the current
        # installation source. This usually means custom user provided URL
        # that is already all configured and we should not touch it.
        restart_thread.assert_not_called()

    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_payload_restart_CDN_test(self, get_proxy, run_task, restart_thread):
        """Test payload restart at unregistration - CDN source."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=None,
                   progress_callback=progress_callback,
                   error_callback=error_callback,
                   restart_payload=True)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # we should have tried to restart the payload due to the
        # source being the CDN, as it is no longer usable without
        # registration and we need payload restart for this
        # to propagate to the Source and Software spokes
        restart_thread.assert_called_once()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_payload_restart_switched_test(self, get_proxy, run_task, restart_thread,
                                                 switch_source):
        """Test payload restart at unregistration - source switched."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=SOURCE_TYPE_CDROM,
                   progress_callback=progress_callback,
                   error_callback=error_callback,
                   restart_payload=True)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # tried to switch back to the CDROM source source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDROM)
        # we should have tried to restart the payload due to the
        # source being switched by the unregistration
        # (happens for the CDROM source at the moment)
        # and we need payload restart for this to propagate
        # to the Source and Software spokes
        restart_thread.assert_called_once()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.payload.manager.payloadMgr.restart_thread")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def unregister_on_payload_restart_test(self, get_proxy, run_task, restart_thread,
                                           switch_source):
        """Test payload restart at unregistration - no restart needed."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_DNF
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_URL
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # run the function
        unregister(payload=payload,
                   overridden_source_type=None,
                   progress_callback=progress_callback,
                   error_callback=error_callback,
                   restart_payload=True)
        # there should be the unregistration & done phases
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.UNREGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # the error callback should not have been called
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # we should not try to switch away from URL source
        switch_source.assert_not_called()
        # we should not have tried to restart the payload
        # as we are on the URL source and we don't need to change
        # anything about it when we unregister
        restart_thread.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.check_simple_content_access_is_enabled")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def register_username_password_sca_test(self, get_proxy, thread_mgr_wait,
                                            run_task, switch_source, check_sca_enabled):
        """Test the register_and_subscribe() helper method - username & password in SCA mode."""
        payload = Mock()
        source_proxy = payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CLOSEST_MIRROR
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # simulate the system being in Simple Content Access mode
        check_sca_enabled.return_value = True
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # and checked for SCA mode
        check_sca_enabled.assert_called_once()
        # system was not registered, so no unregistration phase and in SCA mode,
        # so also no subscription phase as everything happens automagically
        # in the registration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterUsernamePasswordWithTask.assert_called_once()
        subscription_proxy.ParseAttachedSubscriptionsWithTask.assert_called_once()
        # and skipped the attach task
        subscription_proxy.AttachSubscriptionWithTask.assert_not_called()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()
