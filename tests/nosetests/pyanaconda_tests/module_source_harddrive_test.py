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

from pyanaconda.core.constants import SOURCE_TYPE_HDD
from unittest.mock import patch, Mock

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_HARDDRIVE
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.harddrive.harddrive import HardDriveSourceModule
from pyanaconda.modules.payloads.source.harddrive.harddrive_interface import \
    HardDriveSourceInterface
from pyanaconda.modules.payloads.source.harddrive.initialization import SetUpHardDriveSourceTask, \
    SetupHardDriveResult
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.common.errors.payload import SourceSetupError

from tests.nosetests.pyanaconda_tests import check_dbus_property, PropertiesChangedCallback


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
            self,
            PAYLOAD_SOURCE_HARDDRIVE,
            self.interface,
            *args, **kwargs
        )

    def type_test(self):
        """Hard drive source has a correct type specified."""
        self.assertEqual(SOURCE_TYPE_HDD, self.interface.Type)

    def description_test(self):
        """Hard drive source description."""
        self.interface.SetPartition("device")
        self.interface.SetDirectory("/directory")
        self.assertEqual("device:/directory", self.interface.Description)

    def empty_properties_test(self):
        """Hard drive source properties are empty when not set."""
        self.assertEqual(self.interface.Partition, "")
        self.assertEqual(self.interface.Directory, "")

    def setting_properties_test(self):
        """Hard drive source properties are correctly set."""
        self._check_dbus_property("Partition", "sdj9")
        self._check_dbus_property("Directory", "somewhere/on/the/partition/is/iso.iso")

    def iso_path_test(self):
        """Hard drive source has a correct iso path."""
        self.assertEqual(self.interface.GetIsoPath(), "")

        self.module._iso_name = "GLaDOS.iso"
        self.interface.SetDirectory("/super/secret/base")
        self.assertEqual(self.interface.GetIsoPath(), "/super/secret/base/GLaDOS.iso")

        self.module._iso_name = ""
        self.interface.SetDirectory("/path/to/install/tree")
        self.assertEqual(self.interface.GetIsoPath(), "")


class HardDriveSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = HardDriveSourceModule()

    def type_test(self):
        """Hard drive source module has a correct type."""
        self.assertEqual(SourceType.HDD, self.module.type)

    def network_required_test(self):
        """Test the property network_required."""
        self.assertEqual(self.module.network_required, False)

    def set_up_with_tasks_test(self):
        """Hard drive source set up task type and amount."""
        task_classes = [
            SetUpHardDriveSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    @patch("os.path.ismount")
    def ready_state_test(self, ismount):
        """Hard drive source ready state for set up."""
        ismount.return_value = False

        self.assertEqual(self.module.get_state(), SourceState.UNREADY)
        ismount.assert_called_once_with(self.module._device_mount)

        ismount.reset_mock()
        ismount.return_value = True

        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(return_value=SetupHardDriveResult("/my/path", ""))
        task.succeeded_signal.emit()

        self.assertEqual(self.module.get_state(), SourceState.READY)
        ismount.assert_called_once_with(self.module._device_mount)

    def return_handler_test(self):
        """Hard drive source setup result propagates back."""
        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(
            return_value=SetupHardDriveResult(iso_mount_location, "iso_name.iso")
        )
        task.succeeded_signal.emit()

        self.assertEqual(self.module.install_tree_path, iso_mount_location)
        self.assertEqual(self.module._iso_name, "iso_name.iso")

    def return_handler_without_iso_test(self):
        """Hard drive source setup result propagates back when no ISO is involved.

        This is happening when installation tree is used instead of ISO image.
        """
        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(
            return_value=SetupHardDriveResult(iso_mount_location, "")
        )
        task.succeeded_signal.emit()

        self.assertEqual(self.module.install_tree_path, iso_mount_location)
        self.assertEqual(self.module._iso_name, "")

    def repr_test(self):
        self.module.set_device("device")
        self.module.set_directory("directory")
        self.module._install_tree_path = "install-tree-path"
        self.assertEqual(
            repr(self.module),
            "Source(type='HDD', partition='device', directory='directory')"
        )


class HardDriveSourceSetupTaskTestCase(unittest.TestCase):

    def setup_install_source_task_name_test(self):
        """Hard drive source setup task name."""
        task = _create_setup_task()
        self.assertEqual(task.name, "Set up Hard drive installation source")

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="skynet.iso")
    def success_find_iso_test(self,
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
        self.assertEqual(result, SetupHardDriveResult(iso_mount_location, "skynet.iso"))

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository",
           return_value=True)
    def success_find_dir_test(self,
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
        self.assertEqual(result, SetupHardDriveResult(device_mount_location + path_on_device, ""))

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.verify_valid_repository",
           return_value=False)
    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.unmount")
    def failure_to_find_anything_test(self,
                                      unmount_mock,
                                      verify_valid_repository_mock,
                                      find_and_mount_iso_image_mock,
                                      find_and_mount_device_mock):
        """Hard drive source setup failure to find anything."""
        task = _create_setup_task()
        with self.assertRaises(SourceSetupError) as cm:
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
        self.assertTrue(str(cm.exception).startswith(
            "Nothing useful found for Hard drive ISO source"
        ))

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.find_and_mount_device",
           return_value=False)
    def failure_to_find_mount_device_test(self, find_and_mount_device_mock):
        """Hard drive source setup failure to find partition device."""
        task = _create_setup_task()
        with self.assertRaises(SourceSetupError) as cm:
            task.run()

        find_and_mount_device_mock.assert_called_once_with(
            device_spec,
            device_mount_location
        )
        self.assertTrue(str(cm.exception).startswith(
            "Could not mount device specified as"
        ))

    @patch("pyanaconda.modules.payloads.source.harddrive.initialization.os.path.ismount",
           return_value=True)
    def failure_mount_already_used_test(self, ismount_mock):
        """Hard drive source setup failure to mount partition device."""
        task = _create_setup_task()
        with self.assertRaises(SourceSetupError) as cm:
            task.run()

        ismount_mock.assert_called_once()  # must die on first check
        self.assertTrue(str(cm.exception).startswith(
            "The mount point"
        ))


class HardDriveSourceTearDownTestCase(unittest.TestCase):

    def setUp(self):
        self.source_module = HardDriveSourceModule()

    def tear_down_task_order_test(self):
        """Hard drive source tear down task order."""
        tasks = self.source_module.tear_down_with_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertIsInstance(tasks[0], TearDownMountTask)
        self.assertIsInstance(tasks[1], TearDownMountTask)
        name_suffixes = ["-iso", "-device"]
        for task, fragment in zip(tasks, name_suffixes):
            self.assertTrue(task._target_mount.endswith(fragment))
