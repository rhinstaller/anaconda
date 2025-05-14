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
from unittest.mock import MagicMock, Mock, call, patch

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    PAYLOAD_TYPE_RPM_OSTREE,
    RHSM_SYSPURPOSE_FILE_PATH,
    SOURCE_TYPE_CDN,
    SOURCE_TYPE_CDROM,
    SOURCE_TYPE_CLOSEST_MIRROR,
    SOURCE_TYPE_URL,
    SUBSCRIPTION_REQUEST_TYPE_ORG_KEY,
    SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD,
    THREAD_WAIT_FOR_CONNECTING_NM,
)
from pyanaconda.core.path import join_paths
from pyanaconda.core.subscription import check_system_purpose_set
from pyanaconda.modules.common.errors.subscription import (
    RegistrationError,
    SatelliteProvisioningError,
    UnregistrationError,
)
from pyanaconda.modules.common.structures.subscription import SubscriptionRequest
from pyanaconda.ui.lib.subscription import (
    SubscriptionPhase,
    check_cdn_is_installation_source,
    org_keys_sufficient,
    register_and_subscribe,
    unregister,
    username_password_sufficient,
)


class CheckSystemPurposeSetTestCase(unittest.TestCase):
    """Test the check_system_purpose_set helper function."""

    def test_check_system_purpose_set(self):
        """Test the check_system_purpose_set() helper function."""
        # system purpose set
        with tempfile.TemporaryDirectory() as sysroot:
            # create a dummy syspurpose file
            syspurpose_path = RHSM_SYSPURPOSE_FILE_PATH
            directory = os.path.split(syspurpose_path)[0]
            os.makedirs(join_paths(sysroot, directory))
            os.mknod(join_paths(sysroot, syspurpose_path))
            assert check_system_purpose_set(sysroot)

        # system purpose not set
        with tempfile.TemporaryDirectory() as sysroot:
            assert not check_system_purpose_set(sysroot)


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
    def test_org_keys_sufficient(self, get_proxy):
        """Test the org_keys_sufficient() helper method."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_REQUEST
        # run the function
        assert org_keys_sufficient()

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_org_keys_sufficient_not_sufficient(self, get_proxy):
        """Test the org_keys_sufficient() helper method - not sufficient."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.KEY_MISSING_REQUEST
        # run the function
        assert not org_keys_sufficient()

    def test_org_keys_sufficient_direct_request(self):
        """Test the org_keys_sufficient() helper method - direct request."""
        # run the function with sufficient authentication data
        request = SubscriptionRequest.from_structure(self.KEY_REQUEST)
        assert org_keys_sufficient(subscription_request=request)
        # run the function with insufficient authentication data
        request = SubscriptionRequest.from_structure(self.KEY_MISSING_REQUEST)
        assert not org_keys_sufficient(subscription_request=request)

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_username_password_sufficient(self, get_proxy):
        """Test the username_password_sufficient() helper method."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_REQUEST
        # run the function
        assert username_password_sufficient()

    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_username_password_sufficient_not_sufficient(self, get_proxy):
        """Test the username_password_sufficient() helper method - not sufficient."""
        subscription_proxy = get_proxy.return_value
        # simulate subscription request
        subscription_proxy.SubscriptionRequest = self.PASSWORD_MISSING_REQUEST
        # run the function
        assert not username_password_sufficient()

    def test_username_password_sufficient_direct_request(self):
        """Test the username_password_sufficient() helper method - direct request."""
        # run the function with sufficient authentication data
        request = SubscriptionRequest.from_structure(self.PASSWORD_REQUEST)
        assert username_password_sufficient(subscription_request=request)
        # run the function with insufficient authentication data
        request = SubscriptionRequest.from_structure(self.PASSWORD_MISSING_REQUEST)
        assert not username_password_sufficient(subscription_request=request)

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_success(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - success."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_register(self, get_proxy, thread_mgr_wait, run_task, switch_source):
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
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_task_failed(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - unregistration failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        # - this should add additional unregister phase and task
        subscription_proxy.IsRegistered = True
        # make the first (unregistration) task fail
        unregistration_error = UnregistrationError("unregistration failed")
        run_task.side_effect = [True, unregistration_error]
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
        error_callback.assert_called_once_with(unregistration_error)
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
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_sat_provisioning_failed(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - Satellite provisioning failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # make the first (registration) task fail
        sat_error = SatelliteProvisioningError("Satellite provisioning failed")
        run_task.side_effect = [True, sat_error]
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
        error_callback.assert_called_once_with(sat_error)
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_failed(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test the register_and_subscribe() helper method - failed to register."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # make the first (registration) task fail
        registration_error = RegistrationError("registration failed")
        run_task.side_effect = [True, registration_error]
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
        error_callback.assert_called_once_with(registration_error)
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # setting CDN as installation source does not make sense
        # when we were not able to attach a subscription
        switch_source.assert_not_called()

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.threading.threadMgr.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_override_cdrom(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                     start_thread):
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
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to override the CDROM source, as it is on a list of sources
        # that are appropriate to be overridden by the CDN source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDN)
        # and tried to run them
        run_task.assert_called()
        # tried to restart the payload as CDN is set and we need to restart
        # the payload to make it usable
        start_thread.assert_called_once()

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_override_cdrom_no_restart(self, get_proxy, thread_mgr_wait, run_task,
                                                switch_source, start_thread):
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
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to override the CDROM source, as it is on a list of sources
        # that are appropriate to be overridden by the CDN source
        switch_source.assert_called_once_with(payload, SOURCE_TYPE_CDN)
        # and tried to run them
        run_task.assert_called()
        # we told the payload not to restart
        start_thread.assert_not_called()

    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister(self, get_proxy, run_task):
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
    def test_unregister_not_registered(self, get_proxy, run_task):
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
    def test_unregister_failed(self, get_proxy, run_task):
        """Test the unregister() helper method - unregistration failed."""
        payload = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system being registered,
        subscription_proxy.IsRegistered = True
        # make the unregistration task fail
        unregistration_error = UnregistrationError("unregistration failed")
        run_task.side_effect = [True, unregistration_error]
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
        error_callback.assert_called_once_with(unregistration_error)
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.UnregisterWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_back_to_cdrom(self, get_proxy, run_task, switch_source):
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

    def test_check_cdn_is_installation_source(self):
        """Test the check_cdn_is_installation_source function."""
        # check CDN is reported as used
        dnf_payload = Mock()
        dnf_payload.type = PAYLOAD_TYPE_DNF
        source_proxy = dnf_payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDN
        assert check_cdn_is_installation_source(dnf_payload)
        # check CDN is not reported as used
        dnf_payload = Mock()
        dnf_payload.type = PAYLOAD_TYPE_DNF
        source_proxy = dnf_payload.get_source_proxy.return_value
        source_proxy.Type = SOURCE_TYPE_CDROM
        assert not check_cdn_is_installation_source(dnf_payload)
        # check an unsupported (non DNF) source is handled correctly
        ostree_payload = Mock()
        ostree_payload.type = PAYLOAD_TYPE_RPM_OSTREE
        assert not check_cdn_is_installation_source(ostree_payload)

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unsupported_payload_reg(self, get_proxy, thread_mgr_wait, run_task, switch_source):
        """Test registration handles unsupported payload."""
        payload = Mock()
        payload.type = PAYLOAD_TYPE_RPM_OSTREE
        progress_callback = Mock()
        error_callback = Mock()
        subscription_proxy = get_proxy.return_value
        # simulate the system not being registered
        subscription_proxy.IsRegistered = False
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unsupported_payload_unregister(self, get_proxy, run_task, switch_source):
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

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_payload_restart(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                      start_thread):
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
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=True)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # tried to restart the payload as CDN is set and we need to restart
        # the payload to make it usable
        start_thread.assert_called_once()

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_payload_no_restart(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                         start_thread):
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
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=False)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # and tried to run them
        run_task.assert_called()
        # told the helper method not to restart
        start_thread.assert_not_called()

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.core.threads.thread_manager.wait")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_register_no_payload_restart(self, get_proxy, thread_mgr_wait, run_task, switch_source,
                                         start_thread):
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
        # run the function
        register_and_subscribe(payload=payload,
                               progress_callback=progress_callback,
                               error_callback=error_callback,
                               restart_payload=True)
        # we should have waited on network
        thread_mgr_wait.assert_called_once_with(THREAD_WAIT_FOR_CONNECTING_NM)
        # system was no registered, so no unregistration phase
        print(error_callback.mock_calls)
        progress_callback.assert_has_calls(
            [call(SubscriptionPhase.REGISTER),
             call(SubscriptionPhase.DONE)]
        )
        # we were successful, so no error callback calls
        error_callback.assert_not_called()
        # we should have requested the appropriate tasks
        subscription_proxy.SetRHSMConfigWithTask.assert_called_once()
        subscription_proxy.RegisterAndSubscribeWithTask.assert_called_once()
        # not tried to set the CDN source
        switch_source.assert_not_called()
        # and tried to run them
        run_task.assert_called()
        # Payload should have not been restarted as URL is the current
        # installation source. This usually means custom user provided URL
        # that is already all configured and we should not touch it.
        start_thread.assert_not_called()

    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_payload_restart_CDN(self, get_proxy, run_task, start_thread):
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
        start_thread.assert_called_once()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_payload_restart_switched(self, get_proxy, run_task, start_thread,
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
        start_thread.assert_called_once()

    @patch("pyanaconda.ui.lib.subscription.switch_source")
    @patch("pyanaconda.payload.manager.payloadMgr.start")
    @patch("pyanaconda.modules.common.task.sync_run_task")
    @patch("pyanaconda.modules.common.constants.services.SUBSCRIPTION.get_proxy")
    def test_unregister_on_payload_restart(self, get_proxy, run_task, start_thread,
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
        start_thread.assert_not_called()
