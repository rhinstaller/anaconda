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
import unittest
from unittest.mock import Mock, patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_HDD
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_HARDDRIVE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.harddrive.harddrive import HardDriveSourceModule
from pyanaconda.modules.payloads.source.harddrive.harddrive_interface import (
    HardDriveSourceInterface,
)
from pyanaconda.modules.payloads.source.harddrive.initialization import (
    SetupHardDriveResult,
    SetUpHardDriveSourceTask,
)
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from tests.unit_tests.pyanaconda_tests import (
    PropertiesChangedCallback,
    check_dbus_property,
)

device_mount_location = "/mnt/put-harddrive-here_device"
iso_mount_location = "/mnt/put-harddrive-here_iso"
device_spec = "partition"
path_on_device = "/direc/tory"


def _create_setup_task():
    return SetUpHardDriveSourceTask(
        device_mount_location,
        iso_mount_location,
        device_spec,
        path_on_device
    )


class HardDriveSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = HardDriveSourceModule()
        self.interface = HardDriveSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_HARDDRIVE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Hard drive source has a correct type specified."""
        assert SOURCE_TYPE_HDD == self.interface.Type

    def test_description(self):
        """Hard drive source description."""
        self.interface.SetPartition("device")
        self.interface.SetDirectory("/directory")
        assert "device:/directory" == self.interface.Description

    def test_empty_properties(self):
        """Hard drive source properties are empty when not set."""
        assert self.interface.Partition == ""
        assert self.interface.Directory == ""

    def test_setting_properties(self):
        """Hard drive source properties are correctly set."""
        self._check_dbus_property("Partition", "sdj9")
        self._check_dbus_property("Directory", "somewhere/on/the/partition/is/iso.iso")

    def test_iso_path(self):
        """Hard drive source has a correct iso path."""
        assert self.interface.GetIsoPath() == ""

        self.module._iso_name = "GLaDOS.iso"
        self.interface.SetDirectory("/super/secret/base")
        assert self.interface.GetIsoPath() == "/super/secret/base/GLaDOS.iso"

        self.module._iso_name = ""
        self.interface.SetDirectory("/path/to/install/tree")
        assert self.interface.GetIsoPath() == ""


class HardDriveSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = HardDriveSourceModule()

    def test_type(self):
        """Hard drive source module has a correct type."""
        assert SourceType.HDD == self.module.type

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is False

    def test_set_up_with_tasks(self):
        """Hard drive source set up task type and amount."""
        task_classes = [
            SetUpHardDriveSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    @patch("os.path.ismount")
    def test_ready_state(self, ismount):
        """Hard drive source ready state for set up."""
        ismount.return_value = False

        assert self.module.get_state() == SourceState.UNREADY
        ismount.assert_called_once_with(self.module._device_mount)

        ismount.reset_mock()
        ismount.return_value = True

        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(return_value=SetupHardDriveResult("/my/path", ""))
        task.succeeded_signal.emit()

        assert self.module.get_state() == SourceState.READY
        ismount.assert_called_once_with(self.module._device_mount)

    def test_return_handler(self):
        """Hard drive source setup result propagates back."""
        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(
            return_value=SetupHardDriveResult(iso_mount_location, "iso_name.iso")
        )
        task.succeeded_signal.emit()

        assert self.module.install_tree_path == iso_mount_location
        assert self.module._iso_name == "iso_name.iso"

    def test_return_handler_without_iso(self):
        """Hard drive source setup result propagates back when no ISO is involved.

        This is happening when installation tree is used instead of ISO image.
        """
        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(
            return_value=SetupHardDriveResult(iso_mount_location, "")
        )
        task.succeeded_signal.emit()

        assert self.module.install_tree_path == iso_mount_location
        assert self.module._iso_name == ""

    def test_repr(self):
        self.module.set_device("device")
        self.module.set_directory("directory")
        self.module._install_tree_path = "install-tree-path"
        assert repr(self.module) == \
            "Source(type='HDD', partition='device', directory='directory')"


class HardDriveSourceSetupTaskTestCase(unittest.TestCase):

    def test_setup_install_source_task_name(self):
        """Hard drive source setup task name."""
        task = _create_setup_task()
        assert task.name == "Set up Hard drive installation source"

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="skynet.iso")
    def test_success_find_iso(self,
                              find_and_mount_iso_image_mock,
                              find_and_mount_device_mock):
        """Hard drive source setup iso found."""
        task = _create_setup_task()
        result = task.run()

        find_and_mount_device_mock.assert_called_once_with(
            device_spec,
            device_mount_location
        )
        find_and_mount_iso_image_mock.assert_called_once_with(
            device_mount_location + path_on_device, iso_mount_location
        )
        assert result == SetupHardDriveResult(iso_mount_location, "skynet.iso")

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository",
           return_value=True)
    def test_success_find_dir(self,
                              verify_valid_repository_mock,
                              find_and_mount_iso_image_mock,
                              find_and_mount_device_mock):
        """Hard drive source setup dir found."""
        task = _create_setup_task()
        result = task.run()

        find_and_mount_device_mock.assert_called_once_with(
            device_spec,
            device_mount_location
        )
        find_and_mount_iso_image_mock.assert_called_once_with(
            device_mount_location + path_on_device, iso_mount_location
        )
        verify_valid_repository_mock.assert_called_once_with(
            device_mount_location + path_on_device
        )
        assert result == SetupHardDriveResult(device_mount_location + path_on_device, "")

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository",
           return_value=False)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.unmount")
    def test_failure_to_find_anything(self,
                                      unmount_mock,
                                      verify_valid_repository_mock,
                                      find_and_mount_iso_image_mock,
                                      find_and_mount_device_mock):
        """Hard drive source setup failure to find anything."""
        task = _create_setup_task()
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        find_and_mount_device_mock.assert_called_once_with(
            device_spec,
            device_mount_location
        )
        find_and_mount_iso_image_mock.assert_called_once_with(
            device_mount_location + path_on_device, iso_mount_location
        )
        verify_valid_repository_mock.assert_called_once_with(
            device_mount_location + path_on_device
        )
        unmount_mock.assert_called_once_with(
            device_mount_location
        )
        assert str(cm.value).startswith(
            "Nothing useful found for Hard drive ISO source"
        )

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=False)
    def test_failure_to_find_mount_device(self, find_and_mount_device_mock):
        """Hard drive source setup failure to find partition device."""
        task = _create_setup_task()
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        find_and_mount_device_mock.assert_called_once_with(
            device_spec,
            device_mount_location
        )
        assert str(cm.value).startswith(
            "Could not mount device specified as"
        )

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.os.path.ismount",
           return_value=True)
    def test_failure_mount_already_used(self, ismount_mock):
        """Hard drive source setup failure to mount partition device."""
        task = _create_setup_task()
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        ismount_mock.assert_called_once()  # must die on first check
        assert str(cm.value).startswith(
            "The mount point"
        )


class HardDriveSourceTearDownTestCase(unittest.TestCase):

    def setUp(self):
        self.source_module = HardDriveSourceModule()

    def test_required_space(self):
        """Test the required_space property."""
        assert self.source_module.required_space == 0

    def test_tear_down_task_order(self):
        """Hard drive source tear down task order."""
        tasks = self.source_module.tear_down_with_tasks()
        assert len(tasks) == 2
        assert isinstance(tasks[0], TearDownMountTask)
        assert isinstance(tasks[1], TearDownMountTask)
        name_suffixes = ["-iso", "-device"]
        for task, fragment in zip(tasks, name_suffixes):
            assert task._target_mount.endswith(fragment)
