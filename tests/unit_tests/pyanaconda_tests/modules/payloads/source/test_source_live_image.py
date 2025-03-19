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
import tempfile
import unittest
import pytest

from unittest.mock import patch, Mock

from dasbus.typing import get_variant, Str, Bool
from requests import RequestException
from pyanaconda.modules.common.errors.payload import SourceSetupError

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_IMAGE, NETWORK_CONNECTION_TIMEOUT
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_IMAGE
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.live_image.initialization import \
    SetUpLocalImageSourceTask, SetUpRemoteImageSourceTask, SetupImageResult
from pyanaconda.modules.payloads.source.live_image.live_image import LiveImageSourceModule
from pyanaconda.modules.payloads.source.live_image.live_image_interface import \
    LiveImageSourceInterface

from tests.unit_tests.pyanaconda_tests import check_dbus_property


class LiveImageSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the live image source."""

    def setUp(self):
        self.module = LiveImageSourceModule()
        self.interface = LiveImageSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_LIVE_IMAGE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert SOURCE_TYPE_LIVE_IMAGE == self.interface.Type

    def test_description(self):
        """Test the Description property."""
        assert "Live image" == self.interface.Description

    def test_configuration(self):
        """Test the configuration property."""
        data = {
            "url": get_variant(Str, "http://my/image.img"),
            "proxy": get_variant(Str, "http://user:pass@example.com/proxy"),
            "checksum": get_variant(Str, "1234567890"),
            "ssl-verification-enabled": get_variant(Bool, False)
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class LiveImageSourceTestCase(unittest.TestCase):
    """Test the live image source module."""

    def setUp(self):
        self.module = LiveImageSourceModule()

    def test_type(self):
        """Test the type property."""
        assert SourceType.LIVE_IMAGE == self.module.type

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

        self.module.configuration.url = "file://my/path"
        assert self.module.network_required is False

        self.module.configuration.url = "http://my/path"
        assert self.module.network_required is True

        self.module.configuration.url = "https://my/path"
        assert self.module.network_required is True

    def test_is_local(self):
        """Test the is_local property."""
        self.module.configuration.url = "file://my/path"
        assert self.module.is_local is True

        self.module.configuration.url = "http://my/path"
        assert self.module.is_local is False

    def test_get_state(self):
        """Test the source state."""
        assert SourceState.NOT_APPLICABLE == self.module.get_state()

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 1024 * 1024 * 1024

        self.module._required_space = 12345
        assert self.module.required_space == 12345

    def test_set_up_with_tasks(self):
        """Test the set-up tasks."""
        self.module.configuration.url = "file://my/path"
        tasks = self.module.set_up_with_tasks()
        assert len(tasks) == 1
        assert isinstance(tasks[0], SetUpLocalImageSourceTask)

        self.module.configuration.url = "http://my/path"
        tasks = self.module.set_up_with_tasks()
        assert len(tasks) == 1
        assert isinstance(tasks[0], SetUpRemoteImageSourceTask)

    @patch.object(SetUpLocalImageSourceTask, "run")
    def test_handle_setup_task_result(self, runner):
        """Test the handler of the set-up tasks."""
        self.module.configuration.url = "file://my/path"
        runner.return_value = SetupImageResult(12345)

        tasks = self.module.set_up_with_tasks()
        for task in tasks:
            task.run_with_signals()

        runner.assert_called_once_with()
        assert self.module.required_space == 12345

    def test_tear_down_with_tasks(self):
        """Test the tear-down tasks."""
        assert self.module.tear_down_with_tasks() == []

    def test_repr(self):
        """Test the string representation."""
        self.module.configuration.url = "file://my/path"
        assert repr(self.module) == str(
            "Source("
            "type='LIVE_IMAGE', "
            "url='file://my/path'"
            ")"
        )


class SetUpLocalImageSourceTaskTestCase(unittest.TestCase):
    """Test a task to set up a local live image."""

    def test_invalid_image(self):
        """Test an invalid image."""
        configuration = LiveImageConfigurationData()
        configuration.url = "file:///my/invalid/path"

        task = SetUpLocalImageSourceTask(configuration)
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        assert str(cm.value) == "File /my/invalid/path does not exist."

    @patch("os.stat")
    def test_empty_image(self, os_stat):
        """Test an empty image."""
        os_stat.return_value = Mock(st_blocks=0)

        with tempfile.NamedTemporaryFile("w") as f:
            # Run the task.
            configuration = LiveImageConfigurationData()
            configuration.url = "file://" + f.name

            task = SetUpLocalImageSourceTask(configuration)
            result = task.run()

            # Check the result.
            assert isinstance(result, SetupImageResult)
            assert result == SetupImageResult(None)

    @patch("os.stat")
    def test_fake_image(self, os_stat):
        """Test a fake image."""
        os_stat.return_value = Mock(st_blocks=2)

        with tempfile.NamedTemporaryFile("w") as f:
            # Create a fake image.
            f.write("MY FAKE IMAGE")
            f.flush()

            # Run the task.
            configuration = LiveImageConfigurationData()
            configuration.url = "file://" + f.name

            task = SetUpLocalImageSourceTask(configuration)
            result = task.run()

            # Check the result.
            assert isinstance(result, SetupImageResult)
            assert result == SetupImageResult(3072)


class SetUpRemoteImageSourceTaskTestCase(unittest.TestCase):
    """Test a task to set up a remote live image."""

    @patch("pyanaconda.modules.payloads.source.live_image.initialization.requests_session")
    def test_failed_request(self, session_getter):
        """Test a request that fails to be send."""
        # Prepare the session.
        session = session_getter.return_value.__enter__.return_value
        session.head.side_effect = RequestException("Fake!")

        # Run the task.
        configuration = LiveImageConfigurationData()
        configuration.url = "http://my/fake/path"

        task = SetUpRemoteImageSourceTask(configuration)
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        # Check the exception.
        assert str(cm.value) == "Error while handling a request: Fake!"

    @patch("pyanaconda.modules.payloads.source.live_image.initialization.requests_session")
    def test_invalid_response(self, session_getter):
        """Test an invalid response."""
        # Prepare the session.
        session = session_getter.return_value.__enter__.return_value
        response = session.head.return_value
        response.status_code = 303

        # Run the task.
        configuration = LiveImageConfigurationData()
        configuration.url = "http://my/fake/path"

        task = SetUpRemoteImageSourceTask(configuration)
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        # Check the exception.
        assert str(cm.value) == "The request has failed: 303"

    @patch("pyanaconda.modules.payloads.source.live_image.initialization.requests_session")
    def test_missing_size(self, session_getter):
        """Test a request with a missing size."""
        # Prepare the session.
        session = session_getter.return_value.__enter__.return_value
        response = session.head.return_value

        response.status_code = 200
        response.headers = {}

        # Run the task.
        configuration = LiveImageConfigurationData()
        configuration.url = "http://my/fake/path"

        task = SetUpRemoteImageSourceTask(configuration)
        result = task.run()

        # Check the result.
        assert isinstance(result, SetupImageResult)
        assert result == SetupImageResult(None)

    @patch("pyanaconda.modules.payloads.source.live_image.initialization.requests_session")
    def test_fake_request(self, session_getter):
        """Test a fake request."""
        # Prepare the session.
        session = session_getter.return_value.__enter__.return_value
        response = session.head.return_value

        response.status_code = 200
        response.headers = {'content-length': 1000}

        # Run the task.
        configuration = LiveImageConfigurationData()
        configuration.url = "http://my/fake/path"

        task = SetUpRemoteImageSourceTask(configuration)
        result = task.run()

        # Check the result.
        assert isinstance(result, SetupImageResult)
        assert result == SetupImageResult(4000)

    @patch("pyanaconda.modules.payloads.source.live_image.initialization.requests_session")
    def test_https_no_verify_ssl(self, session_getter):
        """Test a request with ssl verification disabled."""
        # Prepare the session.
        session = session_getter.return_value.__enter__.return_value
        response = session.head.return_value

        response.status_code = 200
        response.headers = {'content-length': 1000}

        # Run the task.
        configuration = LiveImageConfigurationData()
        configuration.url = "https://my/fake/path"
        configuration.ssl_verification_enabled = False

        task = SetUpRemoteImageSourceTask(configuration)
        result = task.run()

        # Check the result.
        assert isinstance(result, SetupImageResult)
        session.head.assert_called_once_with(
            url="https://my/fake/path",
            proxies={},
            verify=False,
            timeout=NETWORK_CONNECTION_TIMEOUT
        )
