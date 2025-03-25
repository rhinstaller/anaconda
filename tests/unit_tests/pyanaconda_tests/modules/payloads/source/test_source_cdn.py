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

from pyanaconda.core.constants import SOURCE_TYPE_CDN
from pyanaconda.modules.payloads.source.cdn.cdn import CDNSourceModule
from pyanaconda.modules.payloads.source.cdn.cdn_interface import CDNSourceInterface


class CDNSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the CDN source module."""

    def setUp(self):
        self.module = CDNSourceModule()
        self.interface = CDNSourceInterface(self.module)

    def test_type(self):
        """Test the type of CDN."""
        assert SOURCE_TYPE_CDN == self.interface.Type

    def test_description(self):
        """Test the description of CDN."""
        assert "Red Hat CDN" == self.interface.Description

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    def test_repr(self):
        assert repr(self.module) == "Source(type='CDN')"
