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

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadKickstartSharedTest, PayloadSharedTest

from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.payload.live_image.live_image import LiveImageModule
from pyanaconda.modules.payloads.payload.live_image.live_image_interface import \
    LiveImageInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory


class LiveImageKSTestCase(unittest.TestCase):

    def setUp(self):
        self.payload_module = PayloadsService()
        self.payload_module_interface = PayloadsInterface(self.payload_module)

        self.shared_tests = PayloadKickstartSharedTest(self.payload_module,
                                                       self.payload_module_interface)

    def _check_source_types(self, *expected_types):
        """Check types of sources attached to the active payload."""
        source_types = [
            s.type for s in self.payload_module.active_payload.sources
        ]
        assert source_types == list(expected_types)

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
        self._check_source_types(SourceType.LIVE_IMAGE)

    def test_liveimg_tar_kickstart(self):
        """Test the liveimg command with tar."""
        ks_in = """
        liveimg --url http://my/super/path.tar
        """
        ks_out = """
        # Use live disk image installation
        liveimg --url="http://my/super/path.tar"
        """
        self.shared_tests.check_kickstart(ks_in, ks_out="", ks_tmp=ks_out)
        self._check_source_types(SourceType.LIVE_TAR)

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


class LiveImageModuleTestCase(unittest.TestCase):

    def setUp(self):
        self.module = LiveImageModule()

    def test_calculate_required_space(self):
        """Test the calculate_required_space method."""
        assert self.module.calculate_required_space() == 0

        source = SourceFactory.create_source(SourceType.LIVE_IMAGE)
        self.module.add_source(source)

        assert self.module.calculate_required_space() == 1024 * 1024 * 1024

    def test_install_with_task_from_tar(self):
        """Test Live Image install with tasks from tarfile."""
        assert self.module.install_with_tasks() == []

    @patch_dbus_publish_object
    def test_install_with_task_from_image(self, publisher):
        """Test Live Image install with tasks from image."""
        assert self.module.install_with_tasks() == []

    @patch_dbus_publish_object
    def test_post_install_with_tasks(self, publisher):
        """Test Live Image post installation configuration task."""
        assert self.module.post_install_with_tasks() == []
