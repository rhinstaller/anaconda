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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
import pytest

from unittest.mock import patch, PropertyMock

from blivet.formats.fs import BTRFS
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler, \
    KickstartSpecificationParser
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.factory import PartitioningFactory


class PartitioningFactoryTestCase(unittest.TestCase):
    """Test the partitioning factory."""

    def test_create_partitioning(self):
        """Test create_partitioning."""
        for method in PartitioningMethod:
            module = PartitioningFactory.create_partitioning(method)
            assert isinstance(module, PartitioningModule)
            assert isinstance(module.for_publication(), PartitioningInterface)
            assert module.partitioning_method == method

    def test_failed_partitioning(self):
        """Test failed create_partitioning."""
        with pytest.raises(ValueError):
            PartitioningFactory.create_partitioning("INVALID")

    @patch.object(BTRFS, "formattable", new_callable=PropertyMock)
    @patch.object(BTRFS, "supported", new_callable=PropertyMock)
    def test_get_method_for_kickstart(self, supported, formattable):
        """Test get_method_for_kickstart."""
        supported.return_value = True
        formattable.return_value = True

        self._check_method(
            PartitioningMethod.AUTOMATIC,
            "autopart"
        )
        self._check_method(
            PartitioningMethod.MANUAL,
            "mount /dev/sda1 /"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "reqpart"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "part /"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "logvol / --name=root --vgname=fedora --size=4000"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "volgroup fedora pv.1 pv.2"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "raid / --level=1 --device=0 raid.01 raid.02"
        )
        self._check_method(
            PartitioningMethod.CUSTOM,
            "btrfs / --subvol --name=root fedora-btrfs"
        )
        self._check_method(
            None,
            ""
        )

    def _check_method(self, method, kickstart):
        """Check the partitioning method of the given kickstart."""
        specification = StorageKickstartSpecification
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)
        parser.readKickstartFromString(kickstart)
        assert method == PartitioningFactory.get_method_for_kickstart(handler)
