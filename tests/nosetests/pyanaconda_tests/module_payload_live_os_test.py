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
from pyanaconda.modules.common.constants.objects import LIVE_OS_HANDLER
from pyanaconda.modules.payload.live.live_os import LiveOSHandlerModule
from pyanaconda.modules.payload.live.live_os_interface import LiveOSHandlerInterface


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
