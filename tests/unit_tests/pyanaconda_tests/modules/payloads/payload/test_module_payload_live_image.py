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

from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.live_image.live_image import LiveImageModule
from pyanaconda.modules.payloads.payload.live_image.live_image_interface import (
    LiveImageInterface,
)
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadKickstartSharedTest,
    PayloadSharedTest,
)


class LiveImageKSTestCase(unittest.TestCase):

    def setUp(self):
        self.payload_module = PayloadsService()
        self.payload_module_interface = PayloadsInterface(self.payload_module)

        self.shared_tests = PayloadKickstartSharedTest(self.payload_module,
                                                       self.payload_module_interface)

    def test_liveimg_simple_kickstart(self):
        """Test the simple liveimg command."""
        ks_in = """
        liveimg --url http://my/super/path
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)

    def test_liveimg_proxy_kickstart(self):
        """Test the liveimg proxy parameter."""
        ks_in = """
        liveimg --url http://my/super/path --proxy=http://ultimate/proxy
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --proxy="http://ultimate/proxy"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)

    def test_liveimg_checksum_kickstart(self):
        """Test the liveimg checksum parameter."""
        ks_in = """
        liveimg --url http://my/super/path --checksum=BATBATBATMAN!
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --checksum="BATBATBATMAN!"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)

    def test_liveimg_noverifyssl_kickstart(self):
        """Test the liveimg noverifyssl parameter."""
        ks_in = """
        liveimg --url http://my/super/path --noverifyssl
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --noverifyssl
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)

    def test_liveimg_complex_kickstart(self):
        """Test the liveimg all parameters."""
        ks_in = """
        liveimg --url http://my/super/path --proxy=http://NO!!!!! --checksum=ABCDEFG --noverifyssl
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path" --proxy="http://NO!!!!!" --noverifyssl --checksum="ABCDEFG"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)


class LiveImageInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_image_module = LiveImageModule()
        self.live_image_interface = LiveImageInterface(self.live_image_module)

        self.shared_tests = PayloadSharedTest(payload=self.live_image_module,
                                              payload_intf=self.live_image_interface)

    def test_type(self):
        self.shared_tests.check_type(PayloadType.LIVE_IMAGE)

    def test_calculate_required_space(self):
        """Test CalculateRequiredTest."""
        assert self.live_image_interface.CalculateRequiredSpace() == 0

        source = SourceFactory.create_source(SourceType.LIVE_IMAGE)
        self.live_image_module.add_source(source)

        assert self.live_image_interface.CalculateRequiredSpace() == 1024 * 1024 * 1024

    # TODO: Add set_source and supported_sources like in Live OS payload when source is available

    @patch_dbus_publish_object
    def test_prepare_system_for_installation_task(self, publisher):
        """Test Live Image is able to create a prepare installation task."""
        # task_path = self.live_image_interface.PreInstallWithTasks()
        # check_task_creation_list(self, task_path, publisher, [SetupInstallationSourceImageTask])
        assert self.live_image_interface.PreInstallWithTasks() == []

    @patch_dbus_publish_object
    def test_install_with_task_from_tar(self, publisher):
        """Test Live Image install with tasks from tarfile."""
        # task_path = self.live_image_interface.InstallWithTasks()
        # check_task_creation_list(self, task_path, publisher, [InstallFromTarTask])
        assert self.live_image_interface.InstallWithTasks() == []

    @patch_dbus_publish_object
    def test_install_with_task_from_image(self, publisher):
        """Test Live Image install with tasks from image."""
        # task_path = self.live_image_interface.InstallWithTasks()
        # check_task_creation_list(self, task_path, publisher, [InstallFromImageTask])
        assert self.live_image_interface.InstallWithTasks() == []

    @patch_dbus_publish_object
    def test_post_install_with_tasks(self, publisher):
        """Test Live Image post installation configuration task."""
        # task_classes = [
        #     CopyDriverDisksFilesTask,
        #     TeardownInstallationSourceImageTask
        # ]
        #
        # task_paths = self.live_image_interface.PostInstallWithTasks()
        #
        # # Check the number of installation tasks.
        # task_number = len(task_classes)
        # self.assertEqual(task_number, len(task_paths))
        # self.assertEqual(task_number, publisher.call_count)
        #
        # # Check the tasks.
        # for i in range(task_number):
        #     object_path, obj = publisher.call_args_list[i][0]
        #     self.assertEqual(object_path, task_paths[i])
        #     self.assertIsInstance(obj, TaskInterface)
        #     self.assertIsInstance(obj.implementation, task_classes[i])
        assert self.live_image_interface.PostInstallWithTasks() == []
