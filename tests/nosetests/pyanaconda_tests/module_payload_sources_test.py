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

from mock import Mock, patch

from pyanaconda.dbus.typing import get_native
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_OS
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payload.base.constants import SourceType
from pyanaconda.modules.payload.sources.live_os import LiveOSSourceModule
from pyanaconda.modules.payload.sources.live_os_interface import LiveOSSourceInterface
from pyanaconda.modules.payload.sources.initialization import SetUpLiveOSSourceTask, \
    TearDownLiveOSSourceTask


class LiveOSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_source_module = LiveOSSourceModule()
        self.live_os_source_interface = LiveOSSourceInterface(self.live_os_source_module)

        self.callback = Mock()
        self.live_os_source_interface.PropertiesChanged.connect(self.callback)

    def type_test(self):
        """Test Live OS source has a correct type specified."""
        self.assertEqual(SourceType.LIVE_OS_IMAGE.value, self.live_os_source_interface.Type)

    def image_path_empty_properties_test(self):
        """Test Live OS handler image path property when not set."""
        self.assertEqual(self.live_os_source_interface.ImagePath, "")

    def image_path_properties_test(self):
        """Test Live OS handler image path property is correctly set."""
        self.live_os_source_interface.SetImagePath("/my/supper/image/path")
        self.assertEqual(self.live_os_source_interface.ImagePath, "/my/supper/image/path")
        self.callback.assert_called_once_with(
            PAYLOAD_SOURCE_LIVE_OS.interface_name, {"ImagePath": "/my/supper/image/path"}, [])

    @patch("pyanaconda.modules.payload.sources.live_os.stat")
    @patch("pyanaconda.modules.payload.sources.live_os.os.stat")
    def detect_live_os_image_failed_block_device_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection failed block device check."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.return_value = {stat_mock.ST_MODE: "whatever"}

        stat_mock.S_ISBLK = Mock()
        stat_mock.S_ISBLK.return_value = False

        self.assertEqual(self.live_os_source_interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payload.sources.live_os.os.stat")
    def detect_live_os_image_failed_nothing_found_test(self, os_stat_mock):
        """Test Live OS image detection failed missing file."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.side_effect = FileNotFoundError()

        self.assertEqual(self.live_os_source_interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payload.sources.live_os.stat")
    @patch("pyanaconda.modules.payload.sources.live_os.os.stat")
    def detect_live_os_image_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        stat_mock.S_ISBLK = Mock(return_value=True)

        detected_image = self.live_os_source_interface.DetectLiveOSImage()
        stat_mock.S_ISBLK.assert_called_once()

        self.assertEqual(detected_image, "/dev/mapper/live-base")


class LiveOSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_source_module = LiveOSSourceModule()

    def type_test(self):
        """Test Live OS source module has a correct type."""
        self.assertEqual(SourceType.LIVE_OS_IMAGE, self.live_os_source_module.type)

    def set_up_with_tasks_test(self):
        """Test Live OS Source set up call."""
        task_classes = [
            SetUpLiveOSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.live_os_source_module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def tear_down_with_tasks_test(self):
        """Test Live OS Source ready state for tear down."""
        task_classes = [
            TearDownLiveOSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.live_os_source_module.tear_down_with_tasks()

        # check the number of tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def ready_state_test(self):
        """Test Live OS Source ready state for set up."""
        callback = Mock()
        self.live_os_source_module.is_ready_changed.connect(callback)

        self.assertFalse(self.live_os_source_module.is_ready)

        tasks = self.live_os_source_module.set_up_with_tasks()

        # tasks were created but not run
        self.assertFalse(self.live_os_source_module.is_ready)
        callback.assert_not_called()

        tasks[-1].succeeded_signal.emit()

        self.assertTrue(self.live_os_source_module.is_ready)
        callback.assert_called_once()

        # tear down task to remove ready state
        callback.reset_mock()

        tasks = self.live_os_source_module.tear_down_with_tasks()

        tasks[-1].succeeded_signal.emit()

        self.assertFalse(self.live_os_source_module.is_ready)
        callback.assert_called_once()


class LiveOSSourceTasksTestCase(unittest.TestCase):

    @patch("pyanaconda.modules.payload.sources.initialization.mount")
    @patch("pyanaconda.modules.payload.sources.initialization.stat")
    @patch("os.stat")
    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS Source setup installation source task."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = get_native(DeviceData.to_structure(device))

        mount.return_value = 0

        SetUpLiveOSSourceTask(
            "/path/to/base/image",
            "/path/to/mount/source/image"
        ).run()

        device_tree.ResolveDevice.assert_called_once_with("/path/to/base/image")
        os_stat.assert_called_once_with("/resolved/path/to/base/image")

    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_missing_image_test(self, proxy_getter):
        """Test Live OS Source setup installation source task missing image error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = ""

        with self.assertRaises(SourceSetupError):
            SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()

    @patch("pyanaconda.modules.payload.sources.initialization.mount")
    @patch("pyanaconda.modules.payload.sources.initialization.stat")
    @patch("os.stat")
    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_failed_to_mount_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS Source setup installation source task mount error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = get_native(DeviceData.to_structure(device))

        mount.return_value = -20

        with self.assertRaises(SourceSetupError):
            SetUpLiveOSSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()
