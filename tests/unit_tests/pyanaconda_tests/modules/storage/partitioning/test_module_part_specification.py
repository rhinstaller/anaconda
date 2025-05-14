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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)

from pyanaconda.modules.storage.partitioning.specification import PartSpec


class PartitioningSpecificationTestCase(unittest.TestCase):
    """Test the PartSpec class."""

    def test_is_partition(self):
        """Test the is_partition method."""
        spec = PartSpec("/")
        assert spec.is_partition(AUTOPART_TYPE_PLAIN) is True
        assert spec.is_partition(AUTOPART_TYPE_LVM) is True
        assert spec.is_partition(AUTOPART_TYPE_LVM_THINP) is True
        assert spec.is_partition(AUTOPART_TYPE_BTRFS) is True

    def test_is_volume(self):
        """Test the is_volume method."""
        spec = PartSpec("/", lv=True)
        assert spec.is_volume(AUTOPART_TYPE_PLAIN) is False
        assert spec.is_volume(AUTOPART_TYPE_LVM) is True
        assert spec.is_volume(AUTOPART_TYPE_LVM_THINP) is True
        assert spec.is_volume(AUTOPART_TYPE_BTRFS) is False

        spec = PartSpec("/", lv=True, thin=True)
        assert spec.is_volume(AUTOPART_TYPE_PLAIN) is False
        assert spec.is_volume(AUTOPART_TYPE_LVM) is True
        assert spec.is_volume(AUTOPART_TYPE_LVM_THINP) is True
        assert spec.is_volume(AUTOPART_TYPE_BTRFS) is False

        spec = PartSpec("/", btr=True)
        assert spec.is_volume(AUTOPART_TYPE_PLAIN) is False
        assert spec.is_volume(AUTOPART_TYPE_LVM) is False
        assert spec.is_volume(AUTOPART_TYPE_LVM_THINP) is False
        assert spec.is_volume(AUTOPART_TYPE_BTRFS) is True

    def test_is_lvm_thin_volume(self):
        """Test the is_lvm_thin_volume method."""
        spec = PartSpec("/", lv=True)
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_PLAIN) is False
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_LVM) is False
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_LVM_THINP) is False
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_BTRFS) is False

        spec = PartSpec("/", lv=True, thin=True)
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_PLAIN) is False
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_LVM) is False
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_LVM_THINP) is True
        assert spec.is_lvm_thin_volume(AUTOPART_TYPE_BTRFS) is False
