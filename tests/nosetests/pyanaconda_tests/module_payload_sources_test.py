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
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payload.sources.live_os import LiveOSSourceModule
from pyanaconda.modules.payload.sources.live_os_interface import LiveOSSourceInterface
from pyanaconda.modules.payload.sources.initialization import SetUpInstallationSourceTask, \
    TearDownInstallationSourceTask


class LiveOSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_source_module = LiveOSSourceModule("/mock/image/path")
        self.live_os_source_interface = LiveOSSourceInterface(self.live_os_source_module)

    @patch("pyanaconda.modules.payload.sources.live_os.stat")
    @patch("pyanaconda.modules.payload.sources.live_os.os.stat")
    def validate_test(self, os_stat_mock, stat_mock):
        """Test Live OS source validation call."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.return_value = {stat_mock.ST_MODE: "evil is near!"}

        stat_mock.S_ISBLK = Mock()
        stat_mock.S_ISBLK.return_value = True

        self.assertTrue(self.live_os_source_interface.Validate())

    def validate_failed_test(self):
        """Test Live OS source failed validation call."""
        self.assertFalse(self.live_os_source_interface.Validate())


class LiveOSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_source_module = LiveOSSourceModule("/mock/image/path")

    def set_up_with_tasks_test(self):
        """Test Live OS Source set up call."""
        task_classes = [
            SetUpInstallationSourceTask
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
            TearDownInstallationSourceTask
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

        SetUpInstallationSourceTask(
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
            SetUpInstallationSourceTask(
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
            SetUpInstallationSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()
