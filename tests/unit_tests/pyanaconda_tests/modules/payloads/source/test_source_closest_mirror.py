#
# Copyright (C) 2020  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#
import unittest

from pyanaconda.core.constants import SOURCE_TYPE_CLOSEST_MIRROR
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_CLOSEST_MIRROR
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror import (
    ClosestMirrorSourceModule,
)
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror_interface import (
    ClosestMirrorSourceInterface,
)
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class ClosestMirrorSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the closest mirror source module."""

    def setUp(self):
        self.module = ClosestMirrorSourceModule()
        self.interface = ClosestMirrorSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_CLOSEST_MIRROR,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the type of CDN."""
        assert self.interface.Type == SOURCE_TYPE_CLOSEST_MIRROR

    def test_description(self):
        """Test the description of CDN."""
        assert self.interface.Description == "Closest mirror"

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_repr(self):
        assert repr(self.module) == "Source(type='CLOSEST_MIRROR')"

    def test_updates_enabled(self):
        """Test the UpdatesEnabled property."""
        self._check_dbus_property(
            "UpdatesEnabled",
            True
        )
