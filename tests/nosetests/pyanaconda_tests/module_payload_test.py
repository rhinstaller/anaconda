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
import os

from unittest import TestCase
from mock import patch
from textwrap import dedent
from tempfile import TemporaryDirectory

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object

from pyanaconda.modules.common.constants.objects import PAYLOAD_DEFAULT, LIVE_OS_HANDLER, \
    LIVE_IMAGE_HANDLER
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadModule
from pyanaconda.modules.payload.handler_factory import HandlerType
from pyanaconda.modules.payload.shared.utils import create_root_dir, write_module_blacklist


class PayloadInterfaceTestCase(TestCase):

    def setUp(self):
        """Set up the payload module."""
        self.payload_module = PayloadModule()
        self.payload_interface = PayloadInterface(self.payload_module)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.payload_interface.KickstartCommands, ['liveimg'])
        self.assertEqual(self.payload_interface.KickstartSections, ["packages"])
        self.assertEqual(self.payload_interface.KickstartAddons, [])

    def no_handler_set_test(self):
        """Test empty string is returned when no handler is set."""
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(), "")

    def generate_kickstart_without_handler_test(self):
        """Test kickstart parsing without handler set."""
        self.assertEqual(self.payload_interface.GenerateKickstart(), "")

    def process_kickstart_with_no_handler_test(self):
        """Test kickstart processing when no handler set or created based on KS data."""
        with self.assertLogs('anaconda.modules.payload.payload', level="WARNING") as log:
            self.payload_interface.ReadKickstart("")

            self.assertTrue(any(map(lambda x: "No handler was created" in x, log.output)))

    @patch_dbus_publish_object
    def is_handler_set_test(self, publisher):
        """Test IsHandlerSet API."""
        self.assertFalse(self.payload_interface.IsHandlerSet())

        self.payload_interface.CreateHandler(HandlerType.DNF.value)
        self.assertTrue(self.payload_interface.IsHandlerSet())

    @patch_dbus_publish_object
    def create_dnf_handler_test(self, publisher):
        """Test creation and publishing of the DNF handler module."""
        self.payload_interface.CreateHandler(HandlerType.DNF.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         PAYLOAD_DEFAULT.object_path)
        # here the publisher is called twice because the Packages section is also published
        self.assertEqual(publisher.call_count, 2)

    @patch_dbus_publish_object
    def create_live_os_handler_test(self, publisher):
        """Test creation and publishing of the Live OS handler module."""
        self.payload_interface.CreateHandler(HandlerType.LIVE_OS.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_OS_HANDLER.object_path)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_live_image_handler_test(self, publisher):
        """Test creation and publishing of the Live image handler module."""
        self.payload_interface.CreateHandler(HandlerType.LIVE_IMAGE.value)
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_IMAGE_HANDLER.object_path)
        publisher.assert_called_once()

    @patch_dbus_publish_object
    def create_invalid_handler_test(self, publisher):
        """Test creation of the not existing handler."""
        with self.assertRaises(ValueError):
            self.payload_interface.CreateHandler("NotAHandler")

    @patch_dbus_publish_object
    def create_multiple_handlers_test(self, publisher):
        """Test creating two handlers."""
        self.payload_interface.CreateHandler(HandlerType.DNF.value)
        self.payload_interface.CreateHandler(HandlerType.LIVE_OS.value)

        # The last one should win
        self.assertEqual(self.payload_interface.GetActiveHandlerPath(),
                         LIVE_OS_HANDLER.object_path)
        self.assertEqual(publisher.call_count, 3)


class PayloadSharedUtilsTest(TestCase):

    @patch('pyanaconda.modules.payload.shared.utils.getSysroot')
    def create_root_test(self, getSysroot):
        """Test payload create root directory function."""
        with TemporaryDirectory() as temp:
            getSysroot.return_value = temp

            create_root_dir()

            root_dir = os.path.join(temp, "/root")

            self.assertTrue(os.path.isdir(root_dir))

    @patch('pyanaconda.modules.payload.shared.utils.flags')
    @patch('pyanaconda.modules.payload.shared.utils.getSysroot')
    def write_module_blacklist_test(self, getSysroot, flags):
        """Test write kernel module blacklist to the install root."""
        with TemporaryDirectory() as temp:
            getSysroot.return_value = temp
            flags.cmdline = {"modprobe.blacklist": "mod1 mod2 nonono_mod"}

            write_module_blacklist()

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            self.assertTrue(os.path.isfile(blacklist_file))

            with open(blacklist_file, "rt") as f:
                expected_content = """
                # Module blacklists written by anaconda
                blacklist mod1
                blacklist mod2
                blacklist nonono_mod
                """
                self.assertEqual(dedent(expected_content).lstrip(), f.read())

    @patch('pyanaconda.modules.payload.shared.utils.flags')
    @patch('pyanaconda.modules.payload.shared.utils.getSysroot')
    def write_empty_module_blacklist_test(self, getSysroot, flags):
        """Test write kernel module blacklist to the install root -- empty list."""
        with TemporaryDirectory() as temp:
            getSysroot.return_value = temp
            flags.cmdline = {}

            write_module_blacklist()

            blacklist_file = os.path.join(temp, "etc/modprobe.d/anaconda-blacklist.conf")

            self.assertFalse(os.path.isfile(blacklist_file))
