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
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest, \
    SourceSharedTest

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.common.task.task_interface import TaskInterface
from pyanaconda.modules.common.constants.objects import LIVE_IMAGE_HANDLER
from pyanaconda.modules.payload.base.initialization import CopyDriverDisksFilesTask, \
    UpdateBLSConfigurationTask
from pyanaconda.modules.payload.base.installation import InstallFromImageTask
from pyanaconda.modules.payload.payload import PayloadService
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payloads.live_image.live_image import LiveImageHandlerModule
from pyanaconda.modules.payload.payloads.live_image.live_image_interface import \
    LiveImageHandlerInterface
from pyanaconda.modules.payload.payloads.live_image.initialization import \
    CheckInstallationSourceImageTask, SetupInstallationSourceImageTask, \
    TeardownInstallationSourceImageTask
from pyanaconda.modules.payload.payloads.live_image.installation import InstallFromTarTask


class LiveImageHandlerKSTestCase(unittest.TestCase):

    def setUp(self):
        self.payload_module = PayloadService()
        self.payload_module_interface = PayloadInterface(self.payload_module)

        self.shared_tests = PayloadSharedTest(self,
                                              self.payload_module,
                                              self.payload_module_interface)

    def _check_properties(self, url, proxy="", checksum="", verifyssl=True):
        handler = self.shared_tests.get_payload_handler()

        self.assertIsInstance(handler, LiveImageHandlerModule)
        intf = LiveImageHandlerInterface(handler)

        self.assertEqual(intf.Url, url)
        self.assertEqual(intf.Proxy, proxy)
        self.assertEqual(intf.Checksum, checksum)
        self.assertEqual(intf.VerifySSL, verifyssl)

    def liveimg_simple_kickstart_test(self):
        """Test the simple liveimg command."""
        ks_in = """
        liveimg --url http://my/super/path
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path")

    def liveimg_proxy_kickstart_test(self):
        """Test the liveimg proxy parameter."""
        ks_in = """
        liveimg --url http://my/super/path --proxy=http://ultimate/proxy
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --proxy="http://ultimate/proxy"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path", proxy="http://ultimate/proxy")

    def liveimg_checksum_kickstart_test(self):
        """Test the liveimg checksum parameter."""
        ks_in = """
        liveimg --url http://my/super/path --checksum=BATBATBATMAN!
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --checksum="BATBATBATMAN!"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path", checksum="BATBATBATMAN!")

    def liveimg_noverifyssl_kickstart_test(self):
        """Test the liveimg noverifyssl parameter."""
        ks_in = """
        liveimg --url http://my/super/path --noverifyssl
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --noverifyssl
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path", verifyssl=False)

    def liveimg_complex_kickstart_test(self):
        """Test the liveimg all parameters."""
        ks_in = """
        liveimg --url http://my/super/path --proxy=http://NO!!!!! --checksum=ABCDEFG --noverifyssl
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --proxy="http://NO!!!!!" --noverifyssl --checksum="ABCDEFG"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path",
                               proxy="http://NO!!!!!",
                               verifyssl=False,
                               checksum="ABCDEFG")


class LiveImageHandlerInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_image_module = LiveImageHandlerModule()
        self.live_image_interface = LiveImageHandlerInterface(self.live_image_module)

        self.source_tests = SourceSharedTest(self,
                                             payload=self.live_image_module,
                                             payload_intf=self.live_image_interface)

        self.callback = Mock()
        self.live_image_interface.PropertiesChanged.connect(self.callback)

    # TODO: Add set_source and supported_sources like in Live OS payload when source is available

    def sources_empty_test(self):
        """Test sources Live Image API for emptiness."""
        self.source_tests.check_empty_sources()

    def default_url_test(self):
        self.assertEqual(self.live_image_interface.Url, "")

    def url_properties_test(self):
        self.live_image_interface.SetUrl("http://OUCH!")
        self.assertEqual(self.live_image_interface.Url, "http://OUCH!")
        self.callback.assert_called_once_with(
            LIVE_IMAGE_HANDLER.interface_name, {"Url": "http://OUCH!"}, [])

    def default_proxy_test(self):
        self.assertEqual(self.live_image_interface.Proxy, "")

    def proxy_properties_test(self):
        self.live_image_interface.SetProxy("http://YAYKS!")
        self.assertEqual(self.live_image_interface.Proxy, "http://YAYKS!")
        self.callback.assert_called_once_with(
            LIVE_IMAGE_HANDLER.interface_name, {"Proxy": "http://YAYKS!"}, [])

    def default_checksum_test(self):
        self.assertEqual(self.live_image_interface.Checksum, "")

    def checksum_properties_test(self):
        self.live_image_interface.SetChecksum("ABC1234")
        self.assertEqual(self.live_image_interface.Checksum, "ABC1234")
        self.callback.assert_called_once_with(
            LIVE_IMAGE_HANDLER.interface_name, {"Checksum": "ABC1234"}, [])

    def default_verifyssl_test(self):
        self.assertTrue(self.live_image_interface.VerifySSL)

    def verifyssl_properties_test(self):
        self.live_image_interface.SetVerifySSL(True)
        self.assertEqual(self.live_image_interface.VerifySSL, True)
        self.callback.assert_called_once_with(
            LIVE_IMAGE_HANDLER.interface_name, {"VerifySSL": True}, [])

    def default_space_required_test(self):
        """Test Live Image RequiredSpace property.

        # TODO: Add a real test for required space property
        """
        self.assertEqual(self.live_image_interface.RequiredSpace, 1024 * 1024 * 1024)

    @patch("pyanaconda.modules.payload.payloads.live_image.live_image.get_kernel_version_list")
    def empty_kernel_version_list_test(self, get_kernel_version_list):
        """Test Live Image empty get kernel version list."""
        self.assertEqual(self.live_image_interface.GetKernelVersionList(), [])

        get_kernel_version_list.return_value = []
        kernel_list_callback = Mock()

        # pylint: disable=no-member
        self.live_image_interface.KernelVersionListChanged.connect(kernel_list_callback)
        self.live_image_interface.UpdateKernelVersionList()

        get_kernel_version_list.assert_called_once_with(INSTALL_TREE)

        self.assertEqual(self.live_image_interface.GetKernelVersionList(), [])
        kernel_list_callback.assert_called_once_with([])

    @patch("pyanaconda.modules.payload.payloads.live_image.live_image.get_kernel_version_list")
    def kernel_version_list_test(self, get_kernel_version_list):
        """Test Live Image get kernel version list."""
        kernel_list = ["kernel-abc", "magic-kernel.fc3000.x86_64", "sad-kernel"]
        get_kernel_version_list.return_value = kernel_list
        kernel_list_callback = Mock()

        # pylint: disable=no-member
        self.live_image_interface.KernelVersionListChanged.connect(kernel_list_callback)
        self.live_image_interface.UpdateKernelVersionList()

        get_kernel_version_list.assert_called_once_with(INSTALL_TREE)

        self.assertListEqual(self.live_image_interface.GetKernelVersionList(), kernel_list)
        kernel_list_callback.assert_called_once_with(kernel_list)

    @patch_dbus_publish_object
    def check_installation_source_task_test(self, publisher):
        """Test Live Image is able to create a check installation source task."""
        task_path = self.live_image_interface.SetupWithTask()

        check_task_creation(self, task_path, publisher, CheckInstallationSourceImageTask)

    @patch_dbus_publish_object
    def prepare_system_for_installation_task_test(self, publisher):
        """Test Live Image is able to create a prepare installation task."""
        task_path = self.live_image_interface.PreInstallWithTask()

        check_task_creation(self, task_path, publisher, SetupInstallationSourceImageTask)

    @patch("pyanaconda.modules.payload.payloads.live_image.live_image.url_target_is_tarfile",
           lambda x: True)
    @patch_dbus_publish_object
    def install_with_task_from_tar_test(self, publisher):
        """Test Live Image install with tasks from tarfile."""
        task_path = self.live_image_interface.InstallWithTask()

        check_task_creation(self, task_path, publisher, InstallFromTarTask)

    @patch("pyanaconda.modules.payload.payloads.live_image.live_image.url_target_is_tarfile",
           lambda x: False)
    @patch_dbus_publish_object
    def install_with_task_from_image_test(self, publisher):
        """Test Live Image install with tasks from image."""
        task_path = self.live_image_interface.InstallWithTask()

        check_task_creation(self, task_path, publisher, InstallFromImageTask)

    @patch_dbus_publish_object
    def post_install_with_tasks_test(self, publisher):
        """Test Live Image post installation configuration task."""
        task_classes = [
            UpdateBLSConfigurationTask,
            CopyDriverDisksFilesTask
        ]

        task_paths = self.live_image_interface.PostInstallWithTasks()

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

    @patch_dbus_publish_object
    def teardown_with_task_test(self, publisher):
        """Test Live Image teardown task creation."""
        task_path = self.live_image_interface.TeardownWithTask()

        check_task_creation(self, task_path, publisher, TeardownInstallationSourceImageTask)
