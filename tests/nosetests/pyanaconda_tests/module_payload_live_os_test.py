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

from tests.nosetests.pyanaconda_tests import check_task_creation, patch_dbus_publish_object

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.dbus.typing import get_native
from pyanaconda.modules.common.constants.objects import LIVE_OS_HANDLER
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payload.base.initialization import PrepareSystemForInstallationTask
from pyanaconda.modules.payload.live.live_os import LiveOSHandlerModule
from pyanaconda.modules.payload.live.live_os_interface import LiveOSHandlerInterface
from pyanaconda.modules.payload.live.initialization import SetupInstallationSourceTask, \
    TeardownInstallationSourceTask
from pyanaconda.modules.payload.live.installation import InstallFromImageTask


class LiveOSHandlerInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_module = LiveOSHandlerModule()
        self.live_os_interface = LiveOSHandlerInterface(self.live_os_module)

        self.callback = Mock()
        self.live_os_interface.PropertiesChanged.connect(self.callback)

    def image_path_empty_properties_test(self):
        """Test Live OS handler image path property when not set."""
        self.assertEqual(self.live_os_interface.ImagePath, "")

    def image_path_properties_test(self):
        """Test Live OS handler image path property is correctly set."""
        self.live_os_interface.SetImagePath("/my/supper/image/path")
        self.assertEqual(self.live_os_interface.ImagePath, "/my/supper/image/path")
        self.callback.assert_called_once_with(
            LIVE_OS_HANDLER.interface_name, {"ImagePath": "/my/supper/image/path"}, [])

    @patch("pyanaconda.modules.payload.live.live_os.get_dir_size")
    def space_required_properties_test(self, get_dir_size_mock):
        """Test Live OS SpaceRequired property."""
        get_dir_size_mock.return_value = 2

        self.assertEqual(self.live_os_interface.SpaceRequired, 2048)

    @patch("pyanaconda.modules.payload.live.live_os.get_kernel_version_list")
    def empty_kernel_version_list_test(self, get_kernel_version_list):
        """Test Live OS empty get kernel version list."""
        self.assertEqual(self.live_os_interface.GetKernelVersionList(), [])

        get_kernel_version_list.return_value = []
        kernel_list_callback = Mock()

        # pylint: disable=no-member
        self.live_os_interface.KernelVersionListChanged.connect(kernel_list_callback)
        self.live_os_interface.UpdateKernelVersionList()

        get_kernel_version_list.assert_called_once_with(INSTALL_TREE)

        self.assertEqual(self.live_os_interface.GetKernelVersionList(), [])
        kernel_list_callback.assert_called_once_with([])

    @patch("pyanaconda.modules.payload.live.live_os.get_kernel_version_list")
    def kernel_version_list_test(self, get_kernel_version_list):
        """Test Live OS get kernel version list."""
        kernel_list = ["kernel-abc", "magic-kernel.fc3000.x86_64", "sad-kernel"]
        get_kernel_version_list.return_value = kernel_list
        kernel_list_callback = Mock()

        # pylint: disable=no-member
        self.live_os_interface.KernelVersionListChanged.connect(kernel_list_callback)
        self.live_os_interface.UpdateKernelVersionList()

        get_kernel_version_list.assert_called_once_with(INSTALL_TREE)

        self.assertListEqual(self.live_os_interface.GetKernelVersionList(), kernel_list)
        kernel_list_callback.assert_called_once_with(kernel_list)

    @patch("pyanaconda.modules.payload.live.live_os.stat")
    @patch("pyanaconda.modules.payload.live.live_os.os.stat")
    def detect_live_os_image_failed_block_device_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection failed block device check."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.return_value = {stat_mock.ST_MODE: "whatever"}

        stat_mock.S_ISBLK = Mock()
        stat_mock.S_ISBLK.return_value = False

        self.assertEqual(self.live_os_interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payload.live.live_os.os.stat")
    def detect_live_os_image_failed_nothing_found_test(self, os_stat_mock):
        """Test Live OS image detection failed missing file."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        os_stat_mock.side_effect = FileNotFoundError()

        self.assertEqual(self.live_os_interface.DetectLiveOSImage(), "")

    @patch("pyanaconda.modules.payload.live.live_os.stat")
    @patch("pyanaconda.modules.payload.live.live_os.os.stat")
    def detect_live_os_image_test(self, os_stat_mock, stat_mock):
        """Test Live OS image detection."""
        # we have to patch this even thought that result is used in another mock
        # otherwise we will skip the whole sequence
        stat_mock.S_ISBLK = Mock(return_value=True)

        detected_image = self.live_os_interface.DetectLiveOSImage()
        stat_mock.S_ISBLK.assert_called_once()

        self.assertEqual(detected_image, "/dev/mapper/live-base")

    @patch_dbus_publish_object
    def setup_installation_source_task_test(self, publisher):
        """Test Live OS is able to create a setup installation source task."""
        task_path = self.live_os_interface.SetupInstallationSourceWithTask()

        check_task_creation(self, task_path, publisher, SetupInstallationSourceTask)

    @patch_dbus_publish_object
    def prepare_system_for_installation_task_test(self, publisher):
        """Test Live OS is able to create a prepare installation task."""
        task_path = self.live_os_interface.PreInstallWithTask()

        check_task_creation(self, task_path, publisher, PrepareSystemForInstallationTask)

    @patch_dbus_publish_object
    def teardown_installation_source_task_test(self, publisher):
        """Test Live OS is able to create a teardown installation source task."""
        task_path = self.live_os_interface.TeardownInstallationSourceWithTask()

        check_task_creation(self, task_path, publisher, TeardownInstallationSourceTask)

    @patch_dbus_publish_object
    def install_with_task_test(self, publisher):
        """Test Live OS install with tasks."""
        task_path = self.live_os_interface.InstallWithTask()

        check_task_creation(self, task_path, publisher, InstallFromImageTask)


class LiveOSHandlerTasksTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_module = LiveOSHandlerModule()
        self.live_os_interface = LiveOSHandlerInterface(self.live_os_module)

        self.callback = Mock()
        self.live_os_interface.PropertiesChanged.connect(self.callback)

    @patch("pyanaconda.modules.payload.live.initialization.mount")
    @patch("pyanaconda.modules.payload.live.initialization.stat")
    @patch("os.stat")
    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS setup installation source task."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = "resolvedDeviceName"

        device = DeviceData()
        device.path = "/resolved/path/to/base/image"

        device_tree.GetDeviceData = Mock()
        device_tree.GetDeviceData.return_value = get_native(DeviceData.to_structure(device))

        mount.return_value = 0

        SetupInstallationSourceTask(
            "/path/to/base/image",
            "/path/to/mount/source/image"
        ).run()

        device_tree.ResolveDevice.assert_called_once_with("/path/to/base/image")
        os_stat.assert_called_once_with("/resolved/path/to/base/image")

    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_missing_image_test(self, proxy_getter):
        """Test Live OS setup installation source task missing image error."""
        device_tree = Mock()
        proxy_getter.return_value = device_tree
        device_tree.ResolveDevice = Mock()
        device_tree.ResolveDevice.return_value = ""

        with self.assertRaises(SourceSetupError):
            SetupInstallationSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()

    @patch("pyanaconda.modules.payload.live.initialization.mount")
    @patch("pyanaconda.modules.payload.live.initialization.stat")
    @patch("os.stat")
    @patch("pyanaconda.dbus.DBus.get_proxy")
    def setup_install_source_task_failed_to_mount_test(self, proxy_getter, os_stat, stat, mount):
        """Test Live OS setup installation source task mount error."""
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
            SetupInstallationSourceTask(
                "/path/to/base/image",
                "/path/to/mount/source/image"
            ).run()
