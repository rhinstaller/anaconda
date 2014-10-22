# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>

# Test that grub installs involving raid work correctly
# These tests do not write anything to the disk and do not require root

from blivet.devices import DiskDevice, PartitionDevice, MDRaidArrayDevice
from blivet.devices import BTRFSVolumeDevice, BTRFSSubVolumeDevice
from blivet.devicelibs.raid import RAID1
from blivet.formats import getFormat
from blivet.size import Size

from pyanaconda.bootloader import GRUB

import unittest

class GRUBRaidSimpleTest(unittest.TestCase):
    def setUp(self):
        """Create some device objects to test with.

            This sets up two disks (sda, sdb). The first partition of each
            is a biosboot partition. The second partitions comprise a RAID1
            array formatted as /boot.

            sda additionally contains a third partition formatted as ext4.
        """

        super(GRUBRaidSimpleTest, self).setUp()

        # Make some disks
        self.sda = DiskDevice(name="sda", size=Size("100 GiB"))
        self.sda.format = getFormat("disklabel")
        self.sdb = DiskDevice(name="sdb", size=Size("100 GiB"))
        self.sdb.format = getFormat("disklabel")

        # Set up biosboot partitions, an mdarray for /boot, and a btrfs array on sda + sdb.
        # Start with the partitions
        self.sda1 = PartitionDevice(name="sda1", parents=[self.sda], size=Size("1 MiB"))
        self.sda1.format = getFormat("biosboot")
        self.sda2 = PartitionDevice(name="sda2", parents=[self.sda], size=Size("500 MiB"))
        self.sda2.format = getFormat("mdmember")
        self.sda4 = PartitionDevice(name="sda4", parents=[self.sda], size=Size("500 MiB"))
        self.sda4.format = getFormat("btrfs")

        self.sdb1 = PartitionDevice(name="sdb1", parents=[self.sdb], size=Size("1 MiB"))
        self.sdb1.format = getFormat("biosboot")
        self.sdb2 = PartitionDevice(name="sdb2", parents=[self.sdb], size=Size("500 MiB"))
        self.sdb2.format = getFormat("mdmember")
        self.sdb4 = PartitionDevice(name="sdb4", parents=[self.sdb], size=Size("4 GiB"))
        self.sdb4.format = getFormat("btrfs")

        # Add an extra partition for /boot on not-RAID
        self.sda3 = PartitionDevice(name="sda3", parents=[self.sda], size=Size("500 MiB"))
        self.sda3.format = getFormat("ext4", mountpoint="/boot")

        # Pretend that the partitions are real with real parent disks
        for part in (self.sda1, self.sda2, self.sda3, self.sda4, self.sdb1, self.sdb2, self.sdb4):
            part.parents = part.req_disks

        self.boot_md = MDRaidArrayDevice(name="md1", parents=[self.sda2, self.sdb2], level=1)
        self.boot_md.format = getFormat("ext4", mountpoint="/boot")

        # Set up the btrfs raid1 volume with a subvolume for /boot
        self.btrfs_volume = BTRFSVolumeDevice(parents=[self.sda4, self.sdb4], dataLevel=RAID1)
        self.btrfs_volume.format = getFormat("btrfs")

        self.boot_btrfs = BTRFSSubVolumeDevice(parents=[self.btrfs_volume])
        self.boot_btrfs.format = getFormat("btrfs", mountpoint="/boot")

        self.grub = GRUB()

    def grub_mbr_partition_test(self):
        """Test installing GRUB to a MBR stage1 and partition stage2"""

        # Test stage1 on sda (MBR), stage2 on sda3.
        # install_targets shouldn't do anything weird because there's no RAID
        self.grub.stage1_device = self.sda
        self.grub.stage2_device = self.sda3

        # Convert install_targets to a set so the order doesn't matter
        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda, self.sda3)])

        self.assertEquals(install_targets, expected_targets)

    def grub_partition_partition_test(self):
        """Test installing GRUB to a partition stage1 and partition stage2"""

        # Test stage1 on sda1 (biosboot), stage2 on sda3.
        # again, what goes in is what should come out
        self.grub.stage1_device = self.sda1
        self.grub.stage2_device = self.sda3

        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda1, self.sda3)])

        self.assertEquals(install_targets, expected_targets)

    def grub_mbr_raid1_test(self):
        """Test installing GRUB to a MBR stage1 and RAID1 stage2"""

        # Test stage1 on sda (MBR), stage2 on /boot RAID
        # install_targets should return two grub installs, one for each disk
        # in the raid. stage1 will be the disk, stage2 will be the raid device.
        self.grub.stage1_device = self.sda
        self.grub.stage2_device = self.boot_md

        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda, self.boot_md), (self.sdb, self.boot_md)])

        self.assertEquals(install_targets, expected_targets)

    def grub_partition_raid1_test(self):
        """Test installing GRUB to a partition stage1 and MBR stage2"""

        # Test stage1 on sda1 (biosboot), stage2 on /boot RAID
        # since stage1 is a non-raid partition, install_targets should return
        # the original (stage1, stage2) and not add any targets.
        self.grub.stage1_device = self.sda1
        self.grub.stage2_device = self.boot_md

        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda1, self.boot_md)])

        self.assertEquals(install_targets, expected_targets)

    def grub_btrfs_test(self):
        """Test installing GRUB to a MBR stage1 and btrfs RAID stage2"""

        # Test stage1 on sda (MBR), stage2 on btrfs /boot RAID
        # install_targets should return two grub installs, one for each disk
        # in the btrfs volume. stage1 will be the disk, stage2 will be the
        # btrfs subvolume.
        self.grub.stage1_device = self.sda
        self.grub.stage2_device = self.boot_btrfs

        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda, self.boot_btrfs), (self.sdb, self.boot_btrfs)])

        self.assertEquals(install_targets, expected_targets)

    def grub_partition_btrfs_test(self):
        """Test installing GRUB to a partition stage1 and MBR stage2"""

        # Test stage1 on sda1 (biosboot), stage2 on btrfs /boot RAID
        # since stage1 is a non-raid partition, install_targets should return
        # the original (stage1, stage2) and not add any targets
        self.grub.stage1_device = self.sda1
        self.grub.stage2_device = self.boot_btrfs

        install_targets = set(self.grub.install_targets)
        expected_targets = set([(self.sda1, self.boot_btrfs)])

        self.assertEquals(install_targets, expected_targets)
