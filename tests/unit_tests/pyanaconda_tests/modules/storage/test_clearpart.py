import unittest
from unittest import mock

import blivet
from blivet.flags import flags
from parted import PARTITION_NORMAL

from pyanaconda.core.constants import (
    CLEAR_PARTITIONS_ALL,
    CLEAR_PARTITIONS_LINUX,
    CLEAR_PARTITIONS_NONE,
)
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.disk_initialization import DiskInitializationConfig

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
        assert not self._can_remove(sda1), \
            "type none should not clear any partitions"
        assert not self._can_remove(sda2), \
            "type none should not clear any partitions"

        self._config.initialize_labels = False
        assert not self._can_remove(sda), \
            "type none should not clear non-empty disks"
        assert not self._can_remove(sdb), \
            "type none should not clear formatting from unpartitioned disks"

        assert not self._can_remove(sdc), \
            "type none should not clear empty disk without initlabel"
        assert not self._can_remove(sdd), \
            "type none should not clear empty partition table without initlabel"

        self._config.initialize_labels = True
        assert not self._can_remove(sda), \
            "type none should not clear non-empty disks even with initlabel"
        assert not self._can_remove(sdb), \
            "type non should not clear formatting from unpartitioned disks even with initlabel"
        assert self._can_remove(sdc), \
            "type none should clear empty disks when initlabel is set"
        assert self._can_remove(sdd), \
            "type none should clear empty partition table when initlabel is set"

        #
        # clearpart type linux
        #
        self._config.initialization_mode = CLEAR_PARTITIONS_LINUX
        assert self._can_remove(sda1), \
            "type linux should clear partitions containing ext4 filesystems"
        assert not self._can_remove(sda2), \
            "type linux should not clear partitions containing vfat filesystems"

        self._config.initialize_labels = False
        assert not self._can_remove(sda), \
            "type linux should not clear non-empty disklabels"
        assert self._can_remove(sdb), \
            "type linux should clear linux-native whole-disk " \
            "formatting regardless of initlabel setting"
        assert not self._can_remove(sdc), \
            "type linux should not clear unformatted disks unless initlabel is set"
        assert not self._can_remove(sdd), \
            "type linux should not clear disks with empty " \
            "partition tables unless initlabel is set"

        self._config.initialize_labels = True
        assert not self._can_remove(sda), \
            "type linux should not clear non-empty disklabels"
        assert self._can_remove(sdb), \
            "type linux should clear linux-native whole-disk " \
            "formatting regardless of initlabel setting"
        assert self._can_remove(sdc), \
            "type linux should clear unformatted disks when initlabel is set"
        assert self._can_remove(sdd), \
            "type linux should clear disks with empty " \
            "partition tables when initlabel is set"

        sda1.protected = True
        assert not self._can_remove(sda1), \
            "protected devices should never be cleared"
        assert not self._can_remove(sda), \
            "disks containing protected devices should never be cleared"
        sda1.protected = False

        #
        # clearpart type all
        #
        self._config.initialization_mode = CLEAR_PARTITIONS_ALL
        assert self._can_remove(sda1), \
            "type all should clear all partitions"
        assert self._can_remove(sda2), \
            "type all should clear all partitions"

        self._config.initialize_labels = False
        assert self._can_remove(sda), \
            "type all should initialize all disks"
        assert self._can_remove(sdb), \
            "type all should initialize all disks"
        assert self._can_remove(sdc), \
            "type all should initialize all disks"
        assert self._can_remove(sdd), \
            "type all should initialize all disks"

        self._config.initialize_labels = True
        assert self._can_remove(sda), \
            "type all should initialize all disks"
        assert self._can_remove(sdb), \
            "type all should initialize all disks"
        assert self._can_remove(sdc), \
            "type all should initialize all disks"
        assert self._can_remove(sdd), \
            "type all should initialize all disks"

        sda1.protected = True
        assert not self._can_remove(sda1), \
            "protected devices should never be cleared"
        assert not self._can_remove(sda), \
            "disks containing protected devices should never be cleared"
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
