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
import unittest
from unittest.mock import patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_NFS, URL_TYPE_MIRRORLIST
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_REPOSITORY
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.nfs.initialization import (
    SetUpNFSSourceResult,
    SetUpNFSSourceTask,
)
from pyanaconda.modules.payloads.source.nfs.nfs import NFSSourceModule
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class NFSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()
        self.interface = self.module.for_publication()

    def test_type(self):
        """Test NFS source has a correct type specified."""
        assert self.interface.Type == SOURCE_TYPE_NFS

    def test_description(self):
        """Test NFS source description."""
        self.module.configuration.url = "nfs:example.com:/path"
        assert self.interface.Description == "NFS server example.com:/path"

    def test_configuration_property(self):
        """Test the configuration property."""
        configuration = RepoConfigurationData()
        configuration.url = "nfs:server:/path"

        structure = RepoConfigurationData.to_structure(
            configuration
        )

        check_dbus_property(
            PAYLOAD_SOURCE_REPOSITORY,
            self.interface,
            "Configuration",
            structure
        )


class NFSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()

    def test_type(self):
        """Test NFS source module has a correct type."""
        assert self.module.type == SourceType.NFS

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is True

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    @patch("os.path.ismount")
    def test_get_state(self, ismount_mock):
        """Test NFS source state."""
        ismount_mock.return_value = False
        assert self.module.get_state() == SourceState.UNREADY

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        configuration = RepoConfigurationData()
        configuration.url = "/my/path"

        for task in self.module.set_up_with_tasks():
            task._set_result(SetUpNFSSourceResult(configuration))
            task.succeeded_signal.emit()

        assert self.module.get_state() == SourceState.READY
        ismount_mock.assert_called_once_with(self.module._device_mount)

    def test_set_up_with_tasks(self):
        """Test NFS Source set up call."""
        task_classes = [
            SetUpNFSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_tear_down_with_tasks(self):
        """Test NFS Source ready state for tear down."""
        task_classes = [
            TearDownMountTask,
            TearDownMountTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.tear_down_with_tasks()

        # check the number of tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_configuration_invalid_protocol(self):
        """Test the source configuration with an invalid protocol."""
        configuration = RepoConfigurationData()
        configuration.url = "cdrom"

        with pytest.raises(InvalidValueError) as cm:
            self.module.set_configuration(configuration)

        assert str(cm.value) == "Invalid protocol of an NFS source: 'cdrom'"

    def test_configuration_invalid_url_type(self):
        """Test the source configuration with an invalid URL type."""
        configuration = RepoConfigurationData()
        configuration.url = "nfs:example.com:/some/path"
        configuration.type = URL_TYPE_MIRRORLIST

        with pytest.raises(InvalidValueError) as cm:
            self.module.set_configuration(configuration)

        assert str(cm.value) == "Invalid URL type of an NFS source: 'MIRRORLIST'"

    def test_repository_configuration(self):
        """Test the repository configuration."""
        configuration = RepoConfigurationData()
        configuration.url = "file:///mnt/device"

        for task in self.module.set_up_with_tasks():
            task._set_result(SetUpNFSSourceResult(configuration))
            task.succeeded_signal.emit()

        assert self.module.repository is configuration

    def test_repr(self):
        """Test the string representation of the NFS source."""
        self.module.configuration.url = "nfs:example.com:/some/path"
        assert repr(self.module) == "Source(type='NFS', url='nfs:example.com:/some/path')"


class NFSSourceSetupTaskTestCase(unittest.TestCase):
    """Test the SetUpNFSSourceTask task."""

    def _run_task(self, url, expected=None):
        """Run the set-up task of the NFS source."""
        configuration = RepoConfigurationData()
        configuration.url = url

        task = SetUpNFSSourceTask(
            configuration=configuration,
            device_mount="/mnt/device",
            iso_mount="/mnt/image",
        )
        result = task.run()

        assert task.name == "Set up an NFS source"
        assert isinstance(result, SetUpNFSSourceResult)
        assert isinstance(result.repository, RepoConfigurationData)
        assert result.repository.url == expected
        assert result.repository is not configuration

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_iso(self, mount_mock, find_image_mock):
        """Test NFS source setup find ISO success"""
        find_image_mock.return_value = "image.iso"

        self._run_task(
            "nfs:example.com:/some/path",
            expected="file:///mnt/image"
        )
        mount_mock.assert_called_once_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="nolock"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device",
            "/mnt/image"
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_path_with_iso(self, mount_mock, find_image_mock):
        """Test NFS source setup when url has ISO in a path success"""
        find_image_mock.return_value = "image.iso"

        self._run_task(
            "nfs:example.com:/path/to/super.iso",
            expected="file:///mnt/image"
        )
        mount_mock.assert_called_once_with(
            "example.com:/path/to",
            "/mnt/device",
            fstype="nfs",
            options="nolock"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device/super.iso",
            "/mnt/image"
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.verify_valid_repository")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_directory(self, mount_mock, find_image_mock, verify_mock):
        """Test NFS source setup find installation tree success"""
        find_image_mock.return_value = ""
        verify_mock.return_value = True

        self._run_task(
            "nfs:example.com:/some/path",
            expected="file:///mnt/device"
        )
        mount_mock.assert_called_once_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="nolock"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device",
            "/mnt/image"
        )
        verify_mock.assert_called_once_with(
            "/mnt/device"
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_options_nolock(self, mount_mock, find_image_mock):
        """Test NFS source setup adding nolock to options"""
        find_image_mock.return_value = "image.iso"

        self._run_task(
            "nfs:timeo=50:example.com:/some/path",
            expected="file:///mnt/image"
        )
        mount_mock.assert_called_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="timeo=50,nolock"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device",
            "/mnt/image"
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_options(self, mount_mock, find_image_mock):
        """Test NFS source setup handling nolock in options"""
        find_image_mock.return_value = "image.iso"

        self._run_task(
            "nfs:nolock,timeo=50:example.com:/some/path",
            expected="file:///mnt/image"
        )
        mount_mock.assert_called_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="nolock,timeo=50"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device",
            "/mnt/image"
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_failure_mount(self, mount_mock):
        """Test NFS source setup failure"""
        mount_mock.side_effect = OSError("Fake error!")

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("nfs:example.com:/some/path")

        mount_mock.assert_called_once_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="nolock"
        )

        msg = "Failed to mount the NFS source at 'nfs:example.com:/some/path': Fake error!"
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.unmount")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.verify_valid_repository")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_failure(self, mount_mock, find_image_mock, verify_mock, unmount_mock):
        """Test NFS can't find anything to install from"""
        verify_mock.return_value = False
        find_image_mock.return_value = ""

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("nfs:example.com:/some/path")

        mount_mock.assert_called_once_with(
            "example.com:/some/path",
            "/mnt/device",
            fstype="nfs",
            options="nolock"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device",
            "/mnt/image"
        )
        verify_mock.assert_called_once_with(
            "/mnt/device"
        )
        unmount_mock.assert_called_once_with(
            "/mnt/device"
        )

        msg = "Nothing useful found for the NFS source at 'nfs:example.com:/some/path'."
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.os.path.ismount")
    def test_failure_mount_already_used(self, ismount_mock):
        """NFS source setup failure to mount partition device."""
        ismount_mock.return_value = True

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("nfs:example.com:/some/path")

        ismount_mock.assert_called_once()
        assert str(cm.value) == "The mount point /mnt/device is already in use."


class NFSSourceTearDownTestCase(unittest.TestCase):

    def setUp(self):
        self.source_module = NFSSourceModule()

    def test_tear_down_task_order(self):
        """NFS source tear down task order."""
        tasks = self.source_module.tear_down_with_tasks()
        assert len(tasks) == 2
        assert isinstance(tasks[0], TearDownMountTask)
        assert isinstance(tasks[1], TearDownMountTask)
        name_suffixes = ["-iso", "-device"]
        for task, fragment in zip(tasks, name_suffixes):
            assert task._target_mount.endswith(fragment)
