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

from pyanaconda.core.constants import SOURCE_TYPE_HDD, URL_TYPE_MIRRORLIST
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_REPOSITORY
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.harddrive.harddrive import HardDriveSourceModule
from pyanaconda.modules.payloads.source.harddrive.initialization import (
    SetupHardDriveResult,
    SetUpHardDriveSourceTask,
)
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class HardDriveSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the HDD source module."""

    def setUp(self):
        self.module = HardDriveSourceModule()
        self.interface = self.module.for_publication()

    def test_type(self):
        """Test the Type DBus property of the HDD source."""
        assert self.interface.Type == SOURCE_TYPE_HDD

    def test_description(self):
        """Test the Description DBus property of the HDD source."""
        self.module.configuration.url = "hd:/dev/sda1:/some/path"
        assert self.interface.Description == "/dev/sda1:/some/path"

    def test_configuration_property(self):
        """Test the Configuration DBus property of the HDD source."""
        configuration = RepoConfigurationData()
        configuration.url = "hd:/dev/sda1:/some/path"

        structure = RepoConfigurationData.to_structure(
            configuration
        )

        check_dbus_property(
            PAYLOAD_SOURCE_REPOSITORY,
            self.interface,
            "Configuration",
            structure
        )

    @patch("pyanaconda.modules.payloads.source.harddrive.harddrive.device_matches")
    def test_get_device_defined(self, device_matches_mock):
        """Test the GetDevice DBus method of the HDD source."""
        device_matches_mock.return_value = []
        assert self.interface.GetDevice() == ""

        self.module.configuration.url = "hd:/dev/sda1"
        device_matches_mock.return_value = ["sda1"]
        assert self.interface.GetDevice() == "sda1"

        self.module.configuration.url = "hd:LABEL=TEST"
        device_matches_mock.return_value = ["sda1", "sda2"]
        assert self.interface.GetDevice() == "sda1"

        self.module.configuration.url = "hd:sdb1"
        device_matches_mock.return_value = []
        assert self.interface.GetDevice() == ""

    def test_get_iso_file(self):
        """Test the GetISOFile DBus method of the HDD source."""
        assert self.interface.GetISOFile() == ""

        self.module._iso_file = "/some/path/example.iso"
        assert self.interface.GetISOFile() == "/some/path/example.iso"


class HardDriveSourceTestCase(unittest.TestCase):
    """Test the HDD source module."""

    def setUp(self):
        self.module = HardDriveSourceModule()

    def test_type(self):
        """Hard drive source module has a correct type."""
        assert self.module.type == SourceType.HDD

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is False

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_set_up_with_tasks(self):
        """Hard drive source set up task type and amount."""
        tasks = self.module.set_up_with_tasks()

        assert len(tasks) == 1
        assert isinstance(tasks[0], SetUpHardDriveSourceTask)

    def test_tear_down_with_tasks(self):
        """Test tear down tasks of the HDD source."""
        mount_points = [
            self.module._iso_mount,
            self.module._device_mount,
        ]

        tasks = self.module.tear_down_with_tasks()
        task_number = len(mount_points)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], TearDownMountTask)
            assert tasks[i]._target_mount == mount_points[i]

    @patch("os.path.ismount")
    def test_get_state(self, ismount):
        """Hard drive source ready state for set up."""
        ismount.return_value = False

        assert self.module.get_state() == SourceState.UNREADY
        ismount.assert_called_once_with(self.module._device_mount)

        ismount.reset_mock()
        ismount.return_value = True

        configuration = RepoConfigurationData()
        configuration.url = "file:///mnt/path"

        for task in self.module.set_up_with_tasks():
            task._set_result(SetupHardDriveResult(configuration, None))
            task.succeeded_signal.emit()

        assert self.module.get_state() == SourceState.READY
        ismount.assert_called_once_with(self.module._device_mount)

    def test_configuration_invalid_protocol(self):
        """Test the source configuration with an invalid protocol."""
        configuration = RepoConfigurationData()
        configuration.url = "cdrom"

        with pytest.raises(InvalidValueError) as cm:
            self.module.set_configuration(configuration)

        assert str(cm.value) == "Invalid protocol of a HDD source: 'cdrom'"

    def test_configuration_invalid_url_type(self):
        """Test the source configuration with an invalid URL type."""
        configuration = RepoConfigurationData()
        configuration.url = "hd:/dev/sda1:/some/path"
        configuration.type = URL_TYPE_MIRRORLIST

        with pytest.raises(InvalidValueError) as cm:
            self.module.set_configuration(configuration)

        assert str(cm.value) == "Invalid URL type of a HDD source: 'MIRRORLIST'"

    def test_repository_configuration(self):
        """Test the repository configuration."""
        configuration = RepoConfigurationData()
        configuration.url = "file:///mnt/image"
        iso_file = "/some/path/example.iso"

        for task in self.module.set_up_with_tasks():
            task._set_result(SetupHardDriveResult(configuration, iso_file))
            task.succeeded_signal.emit()

        assert self.module.repository is configuration
        assert self.module.get_iso_file() == iso_file

    def test_repr(self):
        """Test the string representation of the HDD source."""
        self.module.configuration.url = "hd:/dev/sda1:/some/path"
        assert repr(self.module) == "Source(type='HDD', url='hd:/dev/sda1:/some/path')"


class HardDriveSourceSetupTaskTestCase(unittest.TestCase):
    """Test the SetUpHardDriveSourceTask task."""

    def _run_task(self, url, expected_location=None, expected_iso_file=None):
        """Run the set-up task of the HDD source."""
        configuration = RepoConfigurationData()
        configuration.url = url

        task = SetUpHardDriveSourceTask(
            configuration=configuration,
            device_mount="/mnt/device",
            iso_mount="/mnt/image",
        )
        result = task.run()

        assert task.name == "Set up a hard drive source"
        assert isinstance(result, SetupHardDriveResult)
        assert isinstance(result.repository, RepoConfigurationData)
        assert result.repository.url == expected_location
        assert result.repository is not configuration
        assert result.iso_file == expected_iso_file

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image")
    def test_success_find_iso(self, find_image_mock, find_device_mock):
        """Hard drive source setup iso found."""
        find_device_mock.return_value = True
        find_image_mock.return_value = "example.iso"

        self._run_task(
            "hd:/dev/sda1:/some/path",
            expected_location="file:///mnt/image",
            expected_iso_file="/some/path/example.iso",
        )
        find_device_mock.assert_called_once_with(
            "/dev/sda1",
            "/mnt/device",
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device/some/path",
            "/mnt/image",
        )

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository")
    def test_success_find_dir(self, verify_mock, find_image_mock, find_device_mock):
        """Hard drive source setup dir found."""
        find_device_mock.return_value = True
        verify_mock.return_value = True
        find_image_mock.return_value = ""

        self._run_task(
            "hd:/dev/sda1:/some/path",
            expected_location="file:///mnt/device/some/path",
            expected_iso_file=None,
        )
        find_device_mock.assert_called_once_with(
            "/dev/sda1",
            "/mnt/device",
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device/some/path",
            "/mnt/image",
        )
        verify_mock.assert_called_once_with(
            "/mnt/device/some/path",
        )

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.unmount")
    def test_failure_to_find_anything(self, unmount_mock, verify_mock, find_image_mock, find_device_mock):
        """Hard drive source setup failure to find anything."""
        find_device_mock.return_value = True
        verify_mock.return_value = False
        find_image_mock.return_value = ""

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("hd:/dev/sda1:/some/path")

        find_device_mock.assert_called_once_with(
            "/dev/sda1",
            "/mnt/device"
        )
        find_image_mock.assert_called_once_with(
            "/mnt/device/some/path",
            "/mnt/image"
        )
        verify_mock.assert_called_once_with(
            "/mnt/device/some/path"
        )
        unmount_mock.assert_called_once_with(
            "/mnt/device"
        )

        msg = "Nothing useful found for the HDD source at '/dev/sda1:/some/path'."
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device")
    def test_failure_to_find_mount_device(self, find_device_mock):
        """Hard drive source setup failure to find partition device."""
        find_device_mock.return_value = False

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("hd:/dev/sda1:/some/path")

        find_device_mock.assert_called_once_with(
            "/dev/sda1",
            "/mnt/device",
        )
        assert str(cm.value) == "Failed to mount the '/dev/sda1' HDD source."

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.os.path.ismount")
    def test_failure_mount_already_used(self, ismount_mock):
        """Hard drive source setup failure to mount partition device."""
        ismount_mock.return_value = True

        with pytest.raises(SourceSetupError) as cm:
            self._run_task("hd:/dev/sda1:/some/path")

        ismount_mock.assert_called_once()
        assert str(cm.value) == "The mount point /mnt/device is already in use."
