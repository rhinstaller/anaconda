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
from unittest.mock import call, DEFAULT, Mock, patch

from pyanaconda.core.constants import SOURCE_TYPE_CDROM
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.cdrom.cdrom import CdromSourceModule
from pyanaconda.modules.payloads.source.cdrom.cdrom_interface import CdromSourceInterface
from pyanaconda.modules.payloads.source.cdrom.initialization import SetUpCdromSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.payload.utils import PayloadSetupError

from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy, PropertiesChangedCallback


class CdromSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = CdromSourceModule()
        self.interface = CdromSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def type_test(self):
        """Test CD-ROM source has a correct type specified."""
        self.assertEqual(SOURCE_TYPE_CDROM, self.interface.Type)

    def device_test(self):
        """Test CD-ROM source Device API."""
        self.assertEqual(self.interface.DeviceName, "")

        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(return_value="top_secret")
        task.succeeded_signal.emit()

        self.assertEqual(self.interface.DeviceName, "top_secret")


class CdromSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = CdromSourceModule()
        self.interface = CdromSourceInterface(self.module)

    def type_test(self):
        """Test CD-ROM source module has a correct type."""
        self.assertEqual(SourceType.CDROM, self.module.type)

    @patch("os.path.ismount")
    def get_state_test(self, ismount_mock):
        """Test CD-ROM source state."""
        ismount_mock.return_value = False
        self.assertEqual(SourceState.UNREADY, self.module.get_state())

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        self.assertEqual(SourceState.READY, self.module.get_state())

        ismount_mock.assert_called_once_with(self.module.mount_point)

    def description_test(self):
        """Hard drive source description."""
        self.assertEqual("Local media", self.interface.Description)

    def network_required_test(self):
        """Test the property network_required."""
        self.assertEqual(self.module.network_required, False)

    def repr_test(self):
        self.assertEqual(repr(self.module), "Source(type='CDROM')")

    def set_up_with_tasks_test(self):
        """Test CD-ROM Source set up call."""
        task_classes = [
            SetUpCdromSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def tear_down_with_tasks_test(self):
        """Test CD-ROM Source ready state for tear down."""
        task_classes = [
            TearDownMountTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.tear_down_with_tasks()

        # check the number of tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])


class CdromSourceSetupTaskTestCase(unittest.TestCase):

    mount_location = "/mnt/put-cdrom-here"

    def setup_install_source_task_name_test(self):
        """Test CD-ROM Source setup installation source task name."""
        task = SetUpCdromSourceTask(self.mount_location)

        self.assertEqual(task.name, "Set up CD-ROM Installation Source")

    @staticmethod
    def set_up_device_tree(num_cdroms):
        """Set up a mock device tree with a specified amount of CD-ROMs.

        Mocks FindOpticalMedia() and GetDeviceData() suitable for testing
        SetUpCdromSourceTask.run()

        :param int num_cdroms: Amount od CD-ROMs
        :return: mock for the device tree
        :rtype: unittest.mock.Mock
        """
        devices = []

        for n in range(num_cdroms):
            device = DeviceData()
            device.name = "test{}".format(n)
            device.path = "/dev/cdrom-test{}".format(n)
            devices.append(device)

        device_tree = Mock()

        device_tree.FindOpticalMedia = Mock()
        device_tree.FindOpticalMedia.return_value = [dev.name for dev in devices]

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.side_effect = [DeviceData.to_structure(dev) for dev in devices]

        return device_tree

    def assert_resolve_and_mount_calls(self,
                                       device_tree_mock, mount_mock,
                                       num_called, num_untouched):
        """Check that a given number of mock CD-ROMs was accessed.

        All devices in the supplied range must have been resolved and mounted (tried to, anyway)
        with GetDeviceData() and mount() respectively. The rest must have been not. The assumption
        is that the called ones precede the untouched ones, because finding a match skips the rest.
        This matches the logic in tested method.
        """
        for n in range(num_called):
            self.assertIn(
                call("test{}".format(n)),
                device_tree_mock.GetDeviceData.mock_calls
            )
            self.assertIn(
                call("/dev/cdrom-test{}".format(n), self.mount_location, "iso9660", "ro"),
                mount_mock.mock_calls
            )

        for n in range(num_called, num_called + num_untouched):
            self.assertNotIn(
                call("test{}".format(n)),
                device_tree_mock.GetDeviceData.mock_calls
            )
            self.assertNotIn(
                call("/dev/cdrom-test{}".format(n), self.mount_location, "iso9660", "ro"),
                mount_mock.mock_calls
            )

        self.assertEqual(device_tree_mock.GetDeviceData.call_count, num_called)
        self.assertEqual(mount_mock.call_count, num_called)

    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.is_valid_install_disk")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.unmount")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.mount")
    @patch_dbus_get_proxy
    def choose_from_multiple_cdroms_test(self, proxy_getter, mount_mock, unmount_mock, valid_mock):
        """Test CD-ROM Source setup installation source task run - choice from multiple CD-ROMs.

        Fake four CD-ROM devices: First fails to mount, second has nothing useful, third has what
        we want so is left mounted, fourth is entirely skipped.
        The other two tests below are needed only to test the exit when nothing is found.
        """
        device_tree = self.set_up_device_tree(4)
        proxy_getter.return_value = device_tree

        mount_mock.side_effect = \
            [PayloadSetupError("Mocked failure"), DEFAULT, DEFAULT, DEFAULT]

        # only for devices 2-4; the expected first call is prevented by the exception from mount
        valid_mock.side_effect = [False, True, False]

        task = SetUpCdromSourceTask(self.mount_location)
        result = task.run()

        # 3/4 devices tried, 1/4 untried
        self.assert_resolve_and_mount_calls(device_tree, mount_mock, 3, 1)

        # Only 2 & 3 were mounted
        self.assertEqual(valid_mock.call_count, 2)
        # It makes no sense to check how validation was called because all mounting is to the same
        # path.

        #  #1 died earlier, #2 was unmounted, #3 was left mounted, #4 never got mounted
        unmount_mock.assert_called_once_with(self.mount_location)

        # Test device name returned
        self.assertEqual(result, "test2")

    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.is_valid_install_disk")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.unmount")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.mount")
    @patch_dbus_get_proxy
    def failure_to_mount_test(self, proxy_getter, mount_mock, unmount_mock, valid_mock):
        """Test CD-ROM Source setup installation source task run - mount failure.

        Mocks one disk which fails to mount, expect exception.
        """
        device_tree = self.set_up_device_tree(1)
        proxy_getter.return_value = device_tree

        mount_mock.side_effect = PayloadSetupError("Mocked failure")
        valid_mock.return_value = True

        with self.assertRaises(SourceSetupError) as cm:
            task = SetUpCdromSourceTask(self.mount_location)
            task.run()

        # 1/1 devices tried, 0 untried
        self.assert_resolve_and_mount_calls(device_tree, mount_mock, 1, 0)
        # neither validation nor unmounting could not have been reached
        valid_mock.assert_not_called()
        unmount_mock.assert_not_called()
        # exception happened due to no disk
        self.assertEqual(str(cm.exception), "Found no CD-ROM")

    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.is_valid_install_disk")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.unmount")
    @patch("pyanaconda.modules.payloads.source.cdrom.initialization.mount")
    @patch_dbus_get_proxy
    def no_cdrom_with_valid_source_test(self, proxy_getter, mount_mock, unmount_mock, valid_mock):
        """Test CD-ROM Source setup installation source task run - no valid source CD-ROMs.

        Mocks one CD-ROM device which has nothing useful, expect exception.
        """
        device_tree = self.set_up_device_tree(1)
        proxy_getter.return_value = device_tree

        valid_mock.return_value = False

        with self.assertRaises(SourceSetupError) as cm:
            task = SetUpCdromSourceTask(self.mount_location)
            task.run()

        # 1/1 devices tried, 0 untried
        self.assert_resolve_and_mount_calls(device_tree, mount_mock, 1, 0)
        # neither validation nor unmounting could not have been reached
        valid_mock.assert_called_once()
        unmount_mock.assert_called_once()
        # exception happened due to no disk
        self.assertEqual(str(cm.exception), "Found no CD-ROM")
