#
# Copyright (C) 2021  Red Hat, Inc.
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
import unittest

from dasbus.typing import get_variant, Str, Bool

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_TAR
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_LIVE_IMAGE
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.live_tar.live_tar import LiveTarSourceModule

from tests.unit_tests.pyanaconda_tests import check_dbus_property


class LiveTarSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the live tar source."""

    def setUp(self):
        self.module = LiveTarSourceModule()
        self.interface = self.module.for_publication()

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_LIVE_IMAGE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == SOURCE_TYPE_LIVE_TAR

    def test_description(self):
        """Test the Description property."""
        assert self.interface.Description == "Live tarball"

    def test_configuration(self):
        """Test the configuration property."""
        data = {
            "url": get_variant(Str, "http://my/image.tar.xz"),
            "proxy": get_variant(Str, "http://user:pass@example.com/proxy"),
            "checksum": get_variant(Str, "1234567890"),
            "ssl-verification-enabled": get_variant(Bool, False)
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class LiveTarSourceTestCase(unittest.TestCase):
    """Test the live tar source module."""

    def setUp(self):
        self.module = LiveTarSourceModule()

    def test_type(self):
        """Test the type property."""
        assert self.module.type == SourceType.LIVE_TAR

    def test_repr(self):
        """Test the string representation."""
        self.module.configuration.url = "file://my/path.tar.xz"
        assert repr(self.module) == str(
            "Source("
            "type='LIVE_TAR', "
            "url='file://my/path.tar.xz'"
            ")"
        )
