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
import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from dasbus.typing import Bool, Str, get_variant
from requests import RequestException

from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT, SOURCE_TYPE_LIVE_IMAGE
from pyanaconda.core.path import join_paths, make_directories, touch
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_IMAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.live_image.initialization import (
    SetupImageResult,
    SetUpLocalImageSourceTask,
    SetUpRemoteImageSourceTask,
)
from pyanaconda.modules.payloads.source.live_image.installation import (
    InstallLiveImageTask,
)
from pyanaconda.modules.payloads.source.live_image.live_image import (
    LiveImageSourceModule,
)
from pyanaconda.modules.payloads.source.live_image.live_image_interface import (
    LiveImageSourceInterface,
)
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


class LiveImageInstallationTestCase(unittest.TestCase):
    """Test the live image installation."""

    def setUp(self):
        """Set up the test."""
        self.data = LiveImageConfigurationData()
        self.directory = None

    @property
    def sysroot(self):
        """The sysroot directory."""
        return join_paths(self.directory, "sysroot")

    @property
    def image(self):
        """The image path."""
        return join_paths(self.directory, "test.img")

    @property
    def mount_point(self):
        """The image mount point."""
        return join_paths(self.directory, "image")

    @contextmanager
    def _create_directory(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory(dir="/var/tmp") as d:
            self.directory = d
            yield
            self.directory = None

    def _create_image(self, files, mount_task_cls):
        """Create a fake image."""
        # Create the image.
        touch(self.image)

        # Set up the configuration data.
        self.data.url = "file://" + self.image

        # Set up the mount point.
        os.makedirs(self.mount_point)

        for path in files:
            file_path = join_paths(self.mount_point, path)
            make_directories(os.path.dirname(file_path))
            touch(file_path)

        mount_task = mount_task_cls()
        mount_task.run.return_value = self.mount_point

    def _run_task(self):
        """Run the task."""
        os.makedirs(self.sysroot)

        task = InstallLiveImageTask(
            sysroot=self.sysroot,
            configuration=self.data
        )

        with patch('pyanaconda.core.dbus.DBus.get_proxy'):
            return task.run()

    def _check_content(self, files):
        """Check the sysroot content."""
        for path in files:
            file_path = join_paths(self.sysroot, path)
            assert os.path.exists(file_path)

    @patch("pyanaconda.modules.payloads.source.live_image.installation.TearDownMountTask")
    @patch("pyanaconda.modules.payloads.source.live_image.installation.MountImageTask")
    def test_install_file(self, mount_task_cls, umount_task_cls):
        """Install a fake image with files."""
        files = ["f1", "f2", "f3"]

        with self._create_directory():
            self._create_image(files, mount_task_cls)
            result = self._run_task()
            self._check_content(files)

        assert result == []

    @patch("pyanaconda.modules.payloads.source.live_image.installation.TearDownMountTask")
    @patch("pyanaconda.modules.payloads.source.live_image.installation.MountImageTask")
    def test_install_kernels(self, mount_task_cls, umount_task_cls):
        """Install a fake image with kernels."""
        files = [
            "/boot/vmlinuz-5.8.15-201.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-6.8.15-201.fc32.x86_64",
            "/boot/vmlinuz-5.8.16-200.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-7.8.16-200.fc32.x86_64",
        ]

        with self._create_directory():
            self._create_image(files, mount_task_cls)
            result = self._run_task()
            self._check_content(files)

        assert result == [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '6.8.15-201.fc32.x86_64',
            '7.8.16-200.fc32.x86_64',
        ]
