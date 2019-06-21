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

from mock import Mock
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadHandlerMixin

from pyanaconda.modules.common.constants.objects import LIVE_IMAGE_HANDLER
from pyanaconda.modules.payload.live.live_image import LiveImageHandlerModule
from pyanaconda.modules.payload.live.live_image_interface import LiveImageHandlerInterface


class LiveImageHandlerKSTestCase(unittest.TestCase, PayloadHandlerMixin):

    def setUp(self):
        self.setup_payload()

    def _check_properties(self, url, proxy="", checksum="", verifyssl=True):
        handler = self.get_payload_handler()

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
        self.check_kickstart(ks_in, ks_out)
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
        self.check_kickstart(ks_in, ks_out)
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
        self.check_kickstart(ks_in, ks_out)
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
        self.check_kickstart(ks_in, ks_out)
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
        self.check_kickstart(ks_in, ks_out)
        self._check_properties(url="http://my/super/path",
                               proxy="http://NO!!!!!",
                               verifyssl=False,
                               checksum="ABCDEFG")


class LiveImageHandlerInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_image_module = LiveImageHandlerModule()
        self.live_image_interface = LiveImageHandlerInterface(self.live_image_module)

        self.callback = Mock()
        self.live_image_interface.PropertiesChanged.connect(self.callback)

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
