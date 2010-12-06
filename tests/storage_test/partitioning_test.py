#!/usr/bin/python

import unittest
from mock import Mock

import parted

import pyanaconda.anaconda_log
pyanaconda.anaconda_log.init()

from pyanaconda.storage.partitioning import getNextPartitionType

# disklabel-type-specific constants
# keys: disklabel type string
# values: 3-tuple of (max_primary_count, supports_extended, max_logical_count)
disklabel_types = {'dos': (4, True, 11),
                   'gpt': (128, False, 0),
                   'mac': (62, False, 0)}

class PartitioningTestCase(unittest.TestCase):
    def getDisk(self, disk_type, primary_count=0,
                has_extended=False, logical_count=0):
        """ Return a mock representing a parted.Disk. """
        disk = Mock()

        disk.type = disk_type
        label_type_info = disklabel_types[disk_type]
        (max_primaries, supports_extended, max_logicals) = label_type_info
        
        # primary partitions
        disk.primaryPartitionCount = primary_count
        disk.maxPrimaryPartitionCount = max_primaries

        # extended partitions
        disk.supportsFeature = Mock(return_value=supports_extended)
        disk.getExtendedPartition = Mock(return_value=has_extended)

        # logical partitions
        disk.getMaxLogicalPartitions = Mock(return_value=max_logicals)
        disk.getLogicalPartitions = Mock(return_value=[0]*logical_count)

        return disk

    def testNextPartitionType(self):
        #
        # DOS
        #
        
        # empty disk, any type
        disk = self.getDisk(disk_type="dos")
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_NORMAL)

        # three primaries and no extended -> extended
        disk = self.getDisk(disk_type="dos", primary_count=3)
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_EXTENDED)

        # three primaries and an extended -> primary
        disk = self.getDisk(disk_type="dos", primary_count=3, has_extended=True)
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_NORMAL)

        # three primaries and an extended w/ no_primary -> logical
        disk = self.getDisk(disk_type="dos", primary_count=3, has_extended=True)
        self.assertEqual(getNextPartitionType(disk, no_primary=True),
                         parted.PARTITION_LOGICAL)

        # four primaries and an extended, available logical -> logical
        disk = self.getDisk(disk_type="dos", primary_count=4, has_extended=True,
                            logical_count=9)
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_LOGICAL)

        # four primaries and an extended, no available logical -> None
        disk = self.getDisk(disk_type="dos", primary_count=4, has_extended=True,
                            logical_count=11)
        self.assertEqual(getNextPartitionType(disk), None)

        # four primaries and no extended -> None
        disk = self.getDisk(disk_type="dos", primary_count=4,
                            has_extended=False)
        self.assertEqual(getNextPartitionType(disk), None)

        # free primary slot, extended, no free logical slot -> primary
        disk = self.getDisk(disk_type="dos", primary_count=3, has_extended=True,
                            logical_count=11)
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_NORMAL)

        # free primary slot, extended, no free logical slot w/ no_primary
        # -> None
        disk = self.getDisk(disk_type="dos", primary_count=3, has_extended=True,
                            logical_count=11)
        self.assertEqual(getNextPartitionType(disk, no_primary=True), None)

        #
        # GPT
        #

        # empty disk, any partition type
        disk = self.getDisk(disk_type="gpt")
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_NORMAL)

        # no empty slots -> None
        disk = self.getDisk(disk_type="gpt", primary_count=128)
        self.assertEqual(getNextPartitionType(disk), None)

        # no_primary -> None
        disk = self.getDisk(disk_type="gpt")
        self.assertEqual(getNextPartitionType(disk, no_primary=True), None)

        #
        # MAC
        #

        # empty disk, any partition type
        disk = self.getDisk(disk_type="mac")
        self.assertEqual(getNextPartitionType(disk), parted.PARTITION_NORMAL)

        # no empty slots -> None
        disk = self.getDisk(disk_type="mac", primary_count=62)
        self.assertEqual(getNextPartitionType(disk), None)

        # no_primary -> None
        disk = self.getDisk(disk_type="mac")
        self.assertEqual(getNextPartitionType(disk, no_primary=True), None)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(PartitioningTestCase)


if __name__ == "__main__":
    unittest.main()
