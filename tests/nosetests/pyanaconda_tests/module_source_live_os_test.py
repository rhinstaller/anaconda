#
# Copyright (C) 2019  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest

from unittest.mock import Mock, patch

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_OS
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.constants import SourceState
from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule
from pyanaconda.modules.payloads.source.live_os.live_os_interface import LiveOSSourceInterface
from pyanaconda.modules.payloads.source.live_os.initialization import SetUpLiveOSSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask

from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy, PropertiesChangedCallback


class LiveOSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = LiveOSSourceModule()
        self.interface = LiveOSSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def type_test(self):
        """Test Live OS source has a correct type specified."""
        self.assertEqual(SOURCE_TYPE_LIVE_OS_IMAGE, self.interface.Type)

    def description_test(self):
        """Test NFS source description."""
        self.assertEqual("Live OS", self.interface.Description)

    def image_path_empty_properties_test(self):
        """Test Live OS payload image path property when not set."""
        self.assertEqual(self.interface.ImagePath, "")

    def image_path_properties_test(self):
        """Test Live OS payload image path property is correctly set."""
        self.interface.SetImagePath("/my/supper/image/path")
        self.assertEqual(self.interface.ImagePath, "/my/supper/image/path")
        self.callback.assert_called_once_with(
            PAYLOAD_SOURCE_LIVE_OS.interface_name, {"ImagePath": "/my/supper/image/path"}, [])

    # TODO: Make detection method coverage better
    @patch("pyanaconda.modules.payloads.source.live_os.live_os.stat")
    @patch("pyanaconda.modules.payloads.source.live_os.live_os.os.stat")
    def detect_live_os_image_failed_block_device_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection failed block device check."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.return_value = {stat_mock.ST_MODE: "whatever"}

        stat_mock.S_ISBLK = Mock()
        stat_mock.S_ISBLK.return_value = False

        self.assertEqual(self.interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payloads.source.live_os.live_os.os.stat")
    def detect_live_os_image_failed_nothing_found_test(self, os_stat_mock):
        """Test Live OS image detection failed missing file."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.side_effect = FileNotFoundError()

        self.assertEqual(self.interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payloads.source.live_os.live_os.stat")
    @patch("pyanaconda.modules.payloads.source.live_os.live_os.os.stat")
    def detect_live_os_image_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        stat_mock.S_ISBLK = Mock(return_value=True)

        detected_image = self.interface.DetectLiveOSImage()
        stat_mock.S_ISBLK.assert_called_once()

        self.assertEqual(detected_image, "/dev/mapper/live-base")


class LiveOSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = LiveOSSourceModule()

    def network_required_test(self):
        """Test the property network_required."""
        self.assertEqual(self.module.network_required, False)

    @patch("os.path.ismount")
    def get_state_test(self, ismount_mock):
        """Test LiveOS source state."""
        ismount_mock.return_value = False
        self.assertEqual(SourceState.UNREADY, self.module.get_state())

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        self.assertEqual(SourceState.READY, self.module.get_state())

        ismount_mock.assert_called_once_with(self.module.mount_point)

    def set_up_with_tasks_test(self):
        """Test Live OS Source set up call."""
        task_classes = [
            SetUpLiveOSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def tear_down_with_tasks_test(self):
        """Test Live OS Source ready state for tear down."""
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

    def repr_test(self):
        self.module.set_image_path("/some/path")
        self.assertEqual(repr(self.module), "Source(type='LIVE_OS_IMAGE', image='/some/path')")


class LiveOSSourceTasksTestCase(unittest.TestCase):

    def setup_install_source_task_name_test(self):
        """Test Live OS Source setup installation source task name."""
        task = SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            )

        self.assertEqual(task.name, "Set up Live OS Installation Source")

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.mount")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.stat")
    @patch("os.stat")
    @patch_dbus_get_proxy
    def setup_install_source_task_run_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS Source setup installation source task run."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = DeviceData.to_structure(device)

        mount.return_value = 0

        SetUpLiveOSSourceTask(
            "/path/to/base/image",
            "/path/to/mount/source/image"
        ).run()

        device_tree.ResolveDevice.assert_called_once_with("/path/to/base/image")
        os_stat.assert_called_once_with("/resolved/path/to/base/image")

    @patch_dbus_get_proxy
    def setup_install_source_task_missing_image_test(self, proxy_getter):
        """Test Live OS Source setup installation source task missing image error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = ""

        with self.assertRaises(SourceSetupError, msg="Failed to find liveOS image!"):
            SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.stat")
    @patch("os.stat")
    @patch_dbus_get_proxy
    def setup_install_source_task_invalid_block_dev_test(self, proxy_getter, os_stat, stat_mock):
        """Test Live OS Source setup installation source task with invalid block device error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = DeviceData.to_structure(device)

        stat_mock.S_ISBLK = Mock()
        stat_mock.S_ISBLK.return_value = False

        with self.assertRaises(SourceSetupError,
                               msg="/path/to/base/image is not a valid block device"):
            SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()

    @patch("pyanaconda.modules.payloads.source.live_os.initialization.mount")
    @patch("pyanaconda.modules.payloads.source.live_os.initialization.stat")
    @patch("os.stat")
    @patch_dbus_get_proxy
    def setup_install_source_task_failed_to_mount_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS Source setup installation source task mount error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = DeviceData.to_structure(device)

        mount.return_value = -20

        with self.assertRaises(SourceSetupError, msg="Failed to mount the install tree"):
            SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()
