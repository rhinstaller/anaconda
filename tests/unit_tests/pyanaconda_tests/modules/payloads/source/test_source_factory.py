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
import pytest

from unittest.case import TestCase

from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.factory import SourceFactory
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.source.source_base_interface import PayloadSourceBaseInterface


class SourceFactoryTestCase(TestCase):
    """Test the source factory."""

    def test_create_source(self):
        """Test SourceFactory create method."""
        for source_type in SourceType:
            module = SourceFactory.create_source(source_type)
            assert isinstance(module, PayloadSourceBase)
            assert isinstance(module.for_publication(), PayloadSourceBaseInterface)
            assert module.type == source_type

    def test_failed_create_source(self):
        """Test failed create method of the source factory."""
        with pytest.raises(ValueError):
            SourceFactory.create_source("INVALID")
