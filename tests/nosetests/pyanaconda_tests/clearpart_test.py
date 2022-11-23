import unittest
import unittest.mock as mock

import blivet

from pyanaconda.modules.storage.disk_initialization import DiskInitializationConfig
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.core.constants import CLEAR_PARTITIONS_ALL, CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_NONE
from parted import PARTITION_NORMAL
from blivet.flags import flags

DEVICE_CLASSES = [
    blivet.devices.DiskDevice,
    blivet.devices.PartitionDevice
]


@unittest.skipUnless(not any(x.unavailable_type_dependencies() for x in DEVICE_CLASSES), "some unsupported device classes required for this test")
class ClearPartTestCase(unittest.TestCase):

    def setUp(self):
        flags.testing = True
        self._storage = create_storage()
        self._config = DiskInitializationConfig()

    def _can_remove(self, device):
        return self._config.can_remove(self._storage, device)

    def test_should_clear(self):
        """ Test the can_remove method. """
        DiskDevice = blivet.devices.DiskDevice
        PartitionDevice = blivet.devices.PartitionDevice

        # sda is a disk with an existing disklabel containing two partitions
        sda = DiskDevice("sda", size=100000, exists=True)
        sda.format = blivet.formats.get_format("disklabel", device=sda.path,
                                               exists=True)
        sda.format._parted_disk = mock.Mock()
        sda.format._parted_device = mock.Mock()
        sda.format._parted_disk.configure_mock(partitions=[])
        self._storage.devicetree._add_device(sda)

        # sda1 is a partition containing an existing ext4 filesystem
        sda1 = PartitionDevice("sda1", size=500, exists=True,
                               parents=[sda])
        sda1._parted_partition = mock.Mock(**{'type': PARTITION_NORMAL,
                                              'getLength.return_value': int(sda1.size),
                                              'getFlag.return_value': 0,
                                              'number': 1})
        sda1.format = blivet.formats.get_format("ext4", mountpoint="/boot",
                                                device=sda1.path,
                                                exists=True)
        self._storage.devicetree._add_device(sda1)

        # sda2 is a partition containing an existing vfat filesystem
        sda2 = PartitionDevice("sda2", size=10000, exists=True,
                               parents=[sda])
        sda2._parted_partition = mock.Mock(**{'type': PARTITION_NORMAL,
                                              'getLength.return_value': int(sda2.size),
                                              'getFlag.return_value': 0,
                                              'number': 2})
        sda2.format = blivet.formats.get_format("vfat", mountpoint="/foo",
                                                device=sda2.path,
                                                exists=True)
        self._storage.devicetree._add_device(sda2)

        # sdb is an unpartitioned disk containing an xfs filesystem
        sdb = DiskDevice("sdb", size=100000, exists=True)
        sdb.format = blivet.formats.get_format("xfs", device=sdb.path,
                                               exists=True)
        self._storage.devicetree._add_device(sdb)

        # sdc is an unformatted/uninitialized/empty disk
        sdc = DiskDevice("sdc", size=100000, exists=True)
        self._storage.devicetree._add_device(sdc)

        # sdd is a disk containing an existing disklabel with no partitions
        sdd = DiskDevice("sdd", size=100000, exists=True)
        sdd.format = blivet.formats.get_format("disklabel", device=sdd.path,
                                               exists=True)
        self._storage.devicetree._add_device(sdd)

        #
        # clearpart type none
        #
        self._config.initialization_mode = CLEAR_PARTITIONS_NONE
        self.assertFalse(self._can_remove(sda1),
                         msg="type none should not clear any partitions")
        self.assertFalse(self._can_remove(sda2),
                         msg="type none should not clear any partitions")

        self._config.initialize_labels = False
        self.assertFalse(self._can_remove(sda),
                         msg="type none should not clear non-empty disks")
        self.assertFalse(self._can_remove(sdb),
                         msg="type none should not clear formatting from "
                             "unpartitioned disks")

        self.assertFalse(self._can_remove(sdc),
                         msg="type none should not clear empty disk without "
                             "initlabel")
        self.assertFalse(self._can_remove(sdd),
                         msg="type none should not clear empty partition table "
                             "without initlabel")

        self._config.initialize_labels = True
        self.assertFalse(self._can_remove(sda),
                         msg="type none should not clear non-empty disks even "
                             "with initlabel")
        self.assertFalse(self._can_remove(sdb),
                         msg="type non should not clear formatting from "
                             "unpartitioned disks even with initlabel")
        self.assertTrue(self._can_remove(sdc),
                        msg="type none should clear empty disks when initlabel "
                            "is set")
        self.assertTrue(self._can_remove(sdd),
                        msg="type none should clear empty partition table when "
                            "initlabel is set")

        #
        # clearpart type linux
        #
        self._config.initialization_mode = CLEAR_PARTITIONS_LINUX
        self.assertTrue(self._can_remove(sda1),
                        msg="type linux should clear partitions containing "
                            "ext4 filesystems")
        self.assertFalse(self._can_remove(sda2),
                         msg="type linux should not clear partitions "
                             "containing vfat filesystems")

        self._config.initialize_labels = False
        self.assertFalse(self._can_remove(sda),
                         msg="type linux should not clear non-empty disklabels")
        self.assertTrue(self._can_remove(sdb),
                        msg="type linux should clear linux-native whole-disk "
                            "formatting regardless of initlabel setting")
        self.assertFalse(self._can_remove(sdc),
                         msg="type linux should not clear unformatted disks "
                             "unless initlabel is set")
        self.assertFalse(self._can_remove(sdd),
                         msg="type linux should not clear disks with empty "
                             "partition tables unless initlabel is set")

        self._config.initialize_labels = True
        self.assertFalse(self._can_remove(sda),
                         msg="type linux should not clear non-empty disklabels")
        self.assertTrue(self._can_remove(sdb),
                        msg="type linux should clear linux-native whole-disk "
                            "formatting regardless of initlabel setting")
        self.assertTrue(self._can_remove(sdc),
                        msg="type linux should clear unformatted disks when "
                        "initlabel is set")
        self.assertTrue(self._can_remove(sdd),
                        msg="type linux should clear disks with empty "
                        "partition tables when initlabel is set")

        sda1.protected = True
        self.assertFalse(self._can_remove(sda1),
                         msg="protected devices should never be cleared")
        self.assertFalse(self._can_remove(sda),
                         msg="disks containing protected devices should never "
                             "be cleared")
        sda1.protected = False

        #
        # clearpart type all
        #
        self._config.initialization_mode = CLEAR_PARTITIONS_ALL
        self.assertTrue(self._can_remove(sda1),
                        msg="type all should clear all partitions")
        self.assertTrue(self._can_remove(sda2),
                        msg="type all should clear all partitions")

        self._config.initialize_labels = False
        self.assertTrue(self._can_remove(sda),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdb),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdc),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdd),
                        msg="type all should initialize all disks")

        self._config.initialize_labels = True
        self.assertTrue(self._can_remove(sda),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdb),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdc),
                        msg="type all should initialize all disks")
        self.assertTrue(self._can_remove(sdd),
                        msg="type all should initialize all disks")

        sda1.protected = True
        self.assertFalse(self._can_remove(sda1),
                         msg="protected devices should never be cleared")
        self.assertFalse(self._can_remove(sda),
                         msg="disks containing protected devices should never "
                             "be cleared")
        sda1.protected = False

        #
        # clearpart type list
        #
        # TODO

    def tearDown(self):
        flags.testing = False

    def test_initialize_disk(self):
        """
            magic partitions
            non-empty partition table
        """
        pass

    def test_recursive_remove(self):
        """
            protected device at various points in stack
        """
        pass
