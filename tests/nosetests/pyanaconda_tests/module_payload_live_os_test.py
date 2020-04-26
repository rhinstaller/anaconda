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

from tests.nosetests.pyanaconda_tests import check_task_creation, check_task_creation_list, \
    patch_dbus_publish_object, PropertiesChangedCallback
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest

from pyanaconda.core.constants import INSTALL_TREE, SOURCE_TYPE_LIVE_OS_IMAGE
from pyanaconda.modules.common.constants.interfaces import PAYLOAD
from pyanaconda.modules.common.errors.payload import SourceSetupError, IncompatibleSourceError
from pyanaconda.modules.common.task.task_interface import TaskInterface
from pyanaconda.modules.payloads.constants import SourceType, PayloadType, SourceState
from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask, \
    CopyDriverDisksFilesTask, SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.base.initialization import UpdateBLSConfigurationTask
from pyanaconda.modules.payloads.base.installation import InstallFromImageTask
from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
from pyanaconda.modules.payloads.payload.live_os.live_os_interface import LiveOSInterface


class LiveOSInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_module = LiveOSModule()
        self.live_os_interface = LiveOSInterface(self.live_os_module)

        self.shared_tests = PayloadSharedTest(self,
                                              payload=self.live_os_module,
                                              payload_intf=self.live_os_interface)

        self.callback = PropertiesChangedCallback()
        self.live_os_interface.PropertiesChanged.connect(self.callback)

    def _prepare_source(self):
        return self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)

    def _prepare_and_use_source(self):
        source = self._prepare_source()
        self.live_os_module.set_sources([source])

        return source

    def type_test(self):
        self.shared_tests.check_type(PayloadType.LIVE_OS)

    def supported_sources_test(self):
        """Test LiveOS supported sources API."""
        self.assertEqual(
            [SOURCE_TYPE_LIVE_OS_IMAGE],
            self.live_os_interface.SupportedSourceTypes)

    @patch_dbus_publish_object
    def set_source_test(self, publisher):
        """Test if set source API of LiveOS payload."""
        sources = [self._prepare_source()]

        self.shared_tests.set_and_check_sources(sources)

    @patch_dbus_publish_object
    def set_multiple_sources_fail_test(self, publisher):
        """Test LiveOS payload can't set multiple sources."""
        paths = [
            self._prepare_source(),
            self._prepare_source()
        ]

        self.shared_tests.set_and_check_sources(paths, exception=IncompatibleSourceError)

    @patch_dbus_publish_object
    def set_when_initialized_source_fail_test(self, publisher):
        """Test LiveOS payload can't set new sources if the old ones are initialized."""
        source1 = self._prepare_source()
        source2 = self._prepare_source()

        self.shared_tests.set_and_check_sources([source1])

        # can't switch source if attached source is ready
        source1.get_state.return_value = SourceState.READY
        self.shared_tests.set_sources([source2], SourceSetupError)
        self.shared_tests.check_sources([source1])

        source1.get_state.return_value = SourceState.UNREADY
        self.shared_tests.set_and_check_sources([source1])

    @patch("pyanaconda.modules.payloads.payload.live_os.live_os.get_dir_size")
    @patch_dbus_publish_object
    def required_space_properties_test(self, publisher, get_dir_size_mock):
        """Test Live OS RequiredSpace property."""
        self.assertEqual(self.live_os_interface.RequiredSpace, 0)

        get_dir_size_mock.return_value = 2
        self._prepare_and_use_source()
        task = self.live_os_module.set_up_sources_with_task()
        task.succeeded_signal.emit()
        self.assertEqual(self.live_os_interface.RequiredSpace, 2048)
        object_path, _ = publisher.call_args[0]
        self.callback.assert_called_once_with(
            PAYLOAD.interface_name,
            {"RequiredSpace": 2048,
             "Sources": [object_path]}, [])

        self.callback.reset_mock()
        task = self.live_os_module.tear_down_sources_with_task()
        task.stopped_signal.emit()
        self.assertEqual(self.live_os_interface.RequiredSpace, 0)
        self.callback.assert_called_once_with(
            PAYLOAD.interface_name,
            {"RequiredSpace": 0},  [])

    @patch("pyanaconda.modules.payloads.payload.live_os.live_os.get_kernel_version_list")
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

    @patch("pyanaconda.modules.payloads.payload.live_os.live_os.get_kernel_version_list")
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

    @patch_dbus_publish_object
    def set_up_installation_sources_task_test(self, publisher):
        """Test Live OS is able to create a set up installation sources task."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.SetUpSourcesWithTask()

        check_task_creation(self, task_path, publisher, SetUpSourcesTask)

    @patch_dbus_publish_object
    def prepare_system_for_installation_task_test(self, publisher):
        """Test Live OS is able to create a prepare installation task."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.PreInstallWithTasks()

        check_task_creation_list(self, task_path, publisher, [PrepareSystemForInstallationTask])

    @patch_dbus_publish_object
    def prepare_system_for_installation_task_no_source_test(self, publisher):
        """Test Live OS prepare installation task with no source fail."""
        with self.assertRaises(SourceSetupError):
            self.live_os_interface.PreInstallWithTasks()

    @patch_dbus_publish_object
    def tear_down_installation_source_task_test(self, publisher):
        """Test Live OS is able to create a tear down installation sources task."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.TearDownSourcesWithTask()

        check_task_creation(self, task_path, publisher, TearDownSourcesTask)

    @patch_dbus_publish_object
    def install_with_task_test(self, publisher):
        """Test Live OS install with tasks."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.InstallWithTasks()

        check_task_creation_list(self, task_path, publisher, [InstallFromImageTask])

    @patch_dbus_publish_object
    def install_with_task_no_source_test(self, publisher):
        """Test Live OS install with tasks with no source fail."""
        with self.assertRaises(SourceSetupError):
            self.live_os_interface.InstallWithTasks()

    @patch_dbus_publish_object
    def post_install_with_tasks_test(self, publisher):
        """Test Live OS post installation configuration task."""
        task_classes = [
            UpdateBLSConfigurationTask,
            CopyDriverDisksFilesTask
        ]

        task_paths = self.live_os_interface.PostInstallWithTasks()

        # Check the number of installation tasks.
        task_number = len(task_classes)
        self.assertEqual(task_number, len(task_paths))
        self.assertEqual(task_number, publisher.call_count)

        # Check the tasks.
        for i in range(task_number):
            object_path, obj = publisher.call_args_list[i][0]
            self.assertEqual(object_path, task_paths[i])
            self.assertIsInstance(obj, TaskInterface)
            self.assertIsInstance(obj.implementation, task_classes[i])
