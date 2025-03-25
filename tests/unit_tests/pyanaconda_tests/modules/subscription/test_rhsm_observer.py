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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest
import pytest

from unittest.mock import patch, Mock, PropertyMock

from dasbus.typing import get_variant, Str
from dasbus.client.observer import DBusObserverError

from pyanaconda.core.constants import RHSM_SERVICE_TIMEOUT
from pyanaconda.modules.subscription.initialization import StartRHSMTask
from pyanaconda.modules.subscription.rhsm_observer import RHSMObserver
from tests.unit_tests.pyanaconda_tests import patch_system_dbus_get_proxy


class StartRHSMTaskTestCase(unittest.TestCase):
    """Test the StartRHSMTask task.

    The StartRHSMTask is pretty closely related to the RHSMObserver,
    so lets test it here.
    """

    @patch_system_dbus_get_proxy
    @patch("pyanaconda.core.util.start_service")
    def test_success(self, start_service, get_proxy):
        """Test StartRHSMTask - successful task."""

        # create the task
        task = StartRHSMTask()
        # simulate successful systemd service start
        start_service.return_value = 0
        # return mock proxy
        config_proxy = Mock()
        get_proxy.return_value = config_proxy
        # run the task and expect it to succeed
        assert task.run()
        # check service was started correctly
        start_service.assert_called_once_with("rhsm.service")
        # check proxy was requested
        get_proxy.assert_called_once_with(
            "com.redhat.RHSM1",
            "/com/redhat/RHSM1/Config",
            "com.redhat.RHSM1.Config",
        )
        # check expected values were set on the RHSM config proxy
        # - logging should be always set to DEBUG
        # - SSL certificate validation should be enabled by default
        #   (insecure == 0)
        config_proxy.SetAll.assert_called_once_with(
            {
                'logging.default_log_level': get_variant(Str, 'DEBUG'),
            },
            ''
        )

    @patch("pyanaconda.modules.common.constants.services.RHSM.get_proxy")
    @patch("pyanaconda.core.util.start_service")
    def test_insecure(self, start_service, get_proxy):
        """Test StartRHSMTask - setting the server.insecure RHSM config key."""
        # create the task & disable SSL certificate validation
        task = StartRHSMTask(verify_ssl=False)
        # simulate successful systemd service start
        start_service.return_value = 0
        # return mock proxy
        config_proxy = Mock()
        get_proxy.return_value = config_proxy
        # run the task and expect it to succeed
        assert task.run()
        # check service was started correctly
        start_service.assert_called_once_with("rhsm.service")
        # check proxy was requested
        get_proxy.assert_called_once()
        # check expected values were set on the RHSM config proxy
        # - logging should be always set to DEBUG
        # - SSL certificate validation should be disabled if requested
        #   (insecure == 1)
        config_proxy.SetAll.assert_called_once_with(
            {
                'logging.default_log_level': get_variant(Str, 'DEBUG'),
                'server.insecure': get_variant(Str, '1'),
            },
            ''
        )

    @patch("pyanaconda.modules.common.constants.services.RHSM.get_proxy")
    @patch("pyanaconda.core.util.start_service")
    def test_unit_start_failed(self, start_service, get_proxy):
        """Test StartRHSMTask - systemd unit failed to start."""

        # create the task
        task = StartRHSMTask()
        # simulate successful systemd service start
        start_service.return_value = 1
        # run the task and expect it to fail
        assert not task.run()
        # check service was started correctly
        start_service.assert_called_once_with("rhsm.service")
        # check proxy was not requested
        get_proxy.assert_not_called()

    def test_is_service_available_success(self):
        """Test StartRHSMTask - test is_service_available() - success."""

        # create the task
        task = StartRHSMTask()
        # fake get_result()
        task.get_result = Mock()
        task.get_result.return_value = True
        # test the method
        assert task.is_service_available(1)

    def test_is_service_available_failure(self):
        """Test StartRHSMTask - test is_service_available() - failure."""

        # create the task
        task = StartRHSMTask()
        # fake get_result()
        task.get_result = Mock()
        task.get_result.return_value = False
        # test the method
        assert not task.is_service_available(1)

    @patch("pyanaconda.threading.threadMgr.get")
    def test_is_service_available_timeout(self, thread_mgr_get):
        """Test StartRHSMTask - test is_service_available() - timeout."""

        # put this into a variable to fit the patch invocation on single line
        is_running_import = 'pyanaconda.modules.common.task.task.Task.is_running'

        with patch(is_running_import, new_callable=PropertyMock) as is_running:
            # fake is_running
            is_running.return_value = True
            # create the task
            task = StartRHSMTask()
            # fake get_result()
            task.get_result = Mock()
            task.get_result.return_value = False
            # make sure is_running is True
            assert task.is_running
            # us a mock thread, so that it's
            # join method exists immediately
            mock_thread = Mock()
            thread_mgr_get.return_value = mock_thread
            # test the method times out
            assert not task.is_service_available(timeout=1.0)
            # check that the mock thread join() was called with expected
            # timeout
            mock_thread.join.assert_called_once_with(1.0)

    @patch("pyanaconda.threading.threadMgr.get")
    def test_is_service_available_waiting(self, thread_mgr_get):
        """Test StartRHSMTask - test is_service_available() - waiting."""

        # put this into a variable to fit the patch invocation on single line
        is_running_import = 'pyanaconda.modules.common.task.task.Task.is_running'
        with patch(is_running_import, new_callable=PropertyMock) as is_running:
            # fake is_running
            is_running.return_value = True
            # create the task
            task = StartRHSMTask()
            # fake get_result()
            task.get_result = Mock()
            task.get_result.return_value = True
            # make sure is_running is True
            assert task.is_running
            # assure is_running switches to False before
            # the method starts waiting on the mock thread
            mock_thread = Mock()

            def set_running_false(thread):
                is_running.return_value = False
                return mock_thread

            thread_mgr_get.side_effect = set_running_false
            # by replacing the thread by Mock instance,
            # we can avoid running the method in a thread
            # as it will join() Mock instance not a real thread
            assert task.is_service_available(timeout=1.0)
            # check that the mock thread was joined with the
            # expected timeout value
            mock_thread.join.assert_called_once_with(1.0)


class RHSMObserverTestCase(unittest.TestCase):
    """Test the service observer."""

    def _setup_observer(self, observer):
        """Set up the observer."""
        observer._service_available = Mock()
        observer._service_unavailable = Mock()
        assert not observer.is_service_available

    def _make_service_available(self, observer):
        """Make the service available."""
        observer._service_name_appeared_callback()
        self._test_if_service_available(observer)

    def _test_if_service_available(self, observer):
        """Test if service is available."""
        assert observer.is_service_available

        observer._service_available.emit.assert_called_once_with(observer)
        observer._service_available.reset_mock()

        observer._service_unavailable.emit.assert_not_called()
        observer._service_unavailable.reset_mock()

    def _make_service_unavailable(self, observer):
        """Make the service unavailable."""
        observer._is_service_available = False
        self._test_if_service_unavailable(observer)

    def _test_if_service_unavailable(self, observer):
        """Test if service is unavailable."""
        assert not observer.is_service_available

        observer._service_available.emit.assert_not_called()
        observer._service_available.reset_mock()

    @patch_system_dbus_get_proxy
    def test_service_available(self, get_proxy):
        """Test that RHSMObserver returns proxy if service is available."""

        startup_check_method = Mock()
        observer = RHSMObserver(startup_check_method)

        self._setup_observer(observer)
        self._make_service_available(observer)

        # check the observer is returning a reasonably looking proxy
        observer.get_proxy("BAZ")
        get_proxy.assert_called_once_with("com.redhat.RHSM1", "BAZ", "BAZ")

    @patch_system_dbus_get_proxy
    def test_service_not_available_success(self, get_proxy):
        """Test that RHSMObserver checks service startup status and succeeds."""

        startup_check_method = Mock()
        # report that startup was successful
        startup_check_method.return_value = True
        observer = RHSMObserver(startup_check_method)

        self._setup_observer(observer)
        self._make_service_unavailable(observer)

        # check the observer is returning a reasonably looking proxy
        observer.get_proxy("BAZ")
        get_proxy.assert_called_once_with("com.redhat.RHSM1", "BAZ", "BAZ")

        # check that the startup check method was called
        startup_check_method.assert_called_once_with(RHSM_SERVICE_TIMEOUT)

    @patch_system_dbus_get_proxy
    def test_service_not_available_failure(self, get_proxy):
        """Test that RHSMObserver checks service startup status and fails."""

        startup_check_method = Mock()
        # report that startup failed
        startup_check_method.return_value = False
        observer = RHSMObserver(startup_check_method)

        self._setup_observer(observer)
        self._make_service_unavailable(observer)
        # DBusObserverError should be raise
        with pytest.raises(DBusObserverError):
            observer.get_proxy("BAZ")
        # the observer should raise the exception before trying to get a proxy
        get_proxy.assert_not_called()

        # check that the startup check method was called
        startup_check_method.assert_called_once_with(RHSM_SERVICE_TIMEOUT)
