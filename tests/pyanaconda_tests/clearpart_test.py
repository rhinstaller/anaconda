import unittest
import mock

import blivet
from pyanaconda.storage.osinstall import InstallerStorage
from pykickstart.constants import CLEARPART_TYPE_ALL, CLEARPART_TYPE_LINUX, CLEARPART_TYPE_NONE
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

    def test_should_clear(self):
        """ Test the Blivet.should_clear method. """
        b = InstallerStorage()

        DiskDevice = blivet.devices.DiskDevice
        PartitionDevice = blivet.devices.PartitionDevice

        # sda is a disk with an existing disklabel containing two partitions
        sda = DiskDevice("sda", size=100000, exists=True)
        sda.format = blivet.formats.get_format("disklabel", device=sda.path,
                                               exists=True)
        sda.format._parted_disk = mock.Mock()
        sda.format._parted_device = mock.Mock()
        sda.format._parted_disk.configure_mock(partitions=[])
        b.devicetree._add_device(sda)

        # sda1 is a partition containing an existing ext4 filesystem
        sda1 = PartitionDevice("sda1", size=500, exists=True,
                               parents=[sda])
        sda1._parted_partition = mock.Mock(**{'type': PARTITION_NORMAL,
                                              'getLength.return_value': int(sda1.size),
                                              'getFlag.return_value': 0})
        sda1.format = blivet.formats.get_format("ext4", mountpoint="/boot",
                                                device=sda1.path,
                                                exists=True)
        b.devicetree._add_device(sda1)

        # sda2 is a partition containing an existing vfat filesystem
        sda2 = PartitionDevice("sda2", size=10000, exists=True,
                               parents=[sda])
        sda2._parted_partition = mock.Mock(**{'type': PARTITION_NORMAL,
                                              'getLength.return_value': int(sda2.size),
                                              'getFlag.return_value': 0})
        sda2.format = blivet.formats.get_format("vfat", mountpoint="/foo",
                                                device=sda2.path,
                                                exists=True)
        b.devicetree._add_device(sda2)

        # sdb is an unpartitioned disk containing an xfs filesystem
        sdb = DiskDevice("sdb", size=100000, exists=True)
        sdb.format = blivet.formats.get_format("xfs", device=sdb.path,
                                               exists=True)
        b.devicetree._add_device(sdb)

        # sdc is an unformatted/uninitialized/empty disk
        sdc = DiskDevice("sdc", size=100000, exists=True)
        b.devicetree._add_device(sdc)

        # sdd is a disk containing an existing disklabel with no partitions
        sdd = DiskDevice("sdd", size=100000, exists=True)
        sdd.format = blivet.formats.get_format("disklabel", device=sdd.path,
                                               exists=True)
        b.devicetree._add_device(sdd)

        #
        # clearpart type none
        #
        b.config.clear_part_type = CLEARPART_TYPE_NONE
        self.assertFalse(b.should_clear(sda1),
                         msg="type none should not clear any partitions")
        self.assertFalse(b.should_clear(sda2),
                         msg="type none should not clear any partitions")

        b.config.initialize_disks = False
        self.assertFalse(b.should_clear(sda),
                         msg="type none should not clear non-empty disks")
        self.assertFalse(b.should_clear(sdb),
                         msg="type none should not clear formatting from "
                             "unpartitioned disks")

        self.assertFalse(b.should_clear(sdc),
                         msg="type none should not clear empty disk without "
                             "initlabel")
        self.assertFalse(b.should_clear(sdd),
                         msg="type none should not clear empty partition table "
                             "without initlabel")

        b.config.initialize_disks = True
        self.assertFalse(b.should_clear(sda),
                         msg="type none should not clear non-empty disks even "
                             "with initlabel")
        self.assertFalse(b.should_clear(sdb),
                         msg="type non should not clear formatting from "
                             "unpartitioned disks even with initlabel")
        self.assertTrue(b.should_clear(sdc),
                        msg="type none should clear empty disks when initlabel "
                            "is set")
        self.assertTrue(b.should_clear(sdd),
                        msg="type none should clear empty partition table when "
                            "initlabel is set")

        #
        # clearpart type linux
        #
        b.config.clear_part_type = CLEARPART_TYPE_LINUX
        self.assertTrue(b.should_clear(sda1),
                        msg="type linux should clear partitions containing "
                            "ext4 filesystems")
        self.assertFalse(b.should_clear(sda2),
                         msg="type linux should not clear partitions "
                             "containing vfat filesystems")

        b.config.initialize_disks = False
        self.assertFalse(b.should_clear(sda),
                         msg="type linux should not clear non-empty disklabels")
        self.assertTrue(b.should_clear(sdb),
                        msg="type linux should clear linux-native whole-disk "
                            "formatting regardless of initlabel setting")
        self.assertFalse(b.should_clear(sdc),
                         msg="type linux should not clear unformatted disks "
                             "unless initlabel is set")
        self.assertFalse(b.should_clear(sdd),
                         msg="type linux should not clear disks with empty "
                             "partition tables unless initlabel is set")

        b.config.initialize_disks = True
        self.assertFalse(b.should_clear(sda),
                         msg="type linux should not clear non-empty disklabels")
        self.assertTrue(b.should_clear(sdb),
                        msg="type linux should clear linux-native whole-disk "
                            "formatting regardless of initlabel setting")
        self.assertTrue(b.should_clear(sdc),
                        msg="type linux should clear unformatted disks when "
                        "initlabel is set")
        self.assertTrue(b.should_clear(sdd),
                        msg="type linux should clear disks with empty "
                        "partition tables when initlabel is set")

        sda1.protected = True
        self.assertFalse(b.should_clear(sda1),
                         msg="protected devices should never be cleared")
        self.assertFalse(b.should_clear(sda),
                         msg="disks containing protected devices should never "
                             "be cleared")
        sda1.protected = False

        #
        # clearpart type all
        #
        b.config.clear_part_type = CLEARPART_TYPE_ALL
        self.assertTrue(b.should_clear(sda1),
                        msg="type all should clear all partitions")
        self.assertTrue(b.should_clear(sda2),
                        msg="type all should clear all partitions")

        b.config.initialize_disks = False
        self.assertTrue(b.should_clear(sda),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdb),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdc),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdd),
                        msg="type all should initialize all disks")

        b.config.initialize_disks = True
        self.assertTrue(b.should_clear(sda),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdb),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdc),
                        msg="type all should initialize all disks")
        self.assertTrue(b.should_clear(sdd),
                        msg="type all should initialize all disks")

        sda1.protected = True
        self.assertFalse(b.should_clear(sda1),
                         msg="protected devices should never be cleared")
        self.assertFalse(b.should_clear(sda),
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
