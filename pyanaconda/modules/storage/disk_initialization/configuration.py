#
# Configuration of the disk initialization.
#
# Copyright (C) 2019 Red Hat, Inc.
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
import parted
from blivet.devices import PartitionDevice

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    CLEAR_PARTITIONS_ALL,
    CLEAR_PARTITIONS_DEFAULT,
    CLEAR_PARTITIONS_LINUX,
    CLEAR_PARTITIONS_LIST,
    CLEAR_PARTITIONS_NONE,
)

log = get_module_logger(__name__)

_all__ = ["DiskInitializationConfig"]


class DiskInitializationConfig:
    """Configuration of the disk initialization."""

    def __init__(self):
        self.initialization_mode = CLEAR_PARTITIONS_DEFAULT
        self.drives_to_clear = []
        self.devices_to_clear = []
        self.initialize_labels = False
        self.format_unrecognized = False
        self.clear_non_existent = False

    def can_remove(self, storage, device):
        """Can the given device be cleared based on the config?

        :param storage: an instance of the Blivet's storage
        :param device: an instance of the device we want to clear
        :return: True or False
        """
        for disk in device.disks:
            # this will not include disks with hidden formats like multipath
            # and firmware raid member disks
            if self.drives_to_clear and disk.device_id not in self.drives_to_clear:
                return False

        if not self.clear_non_existent:
            if (device.is_disk and not device.format.exists) or \
               (not device.is_disk and not device.exists):
                return False

        # the only devices we want to clear when initialization_mode is
        # CLEAR_PARTITIONS_NONE are uninitialized disks, or disks with no
        # partitions, in drives_to_clear, and then only when we have been asked
        # to initialize disks as needed
        if self.initialization_mode in [CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_DEFAULT]:
            if not self.initialize_labels or not device.is_disk:
                return False

            if not device.is_empty:
                return False

        if isinstance(device, PartitionDevice):
            # Never clear the special first partition on a Mac disk label, as
            # that holds the partition table itself.
            # Something similar for the third partition on a Sun disklabel.
            if device.is_magic:
                return False

            # We don't want to fool with extended partitions, freespace, &c
            if not device.is_primary and not device.is_logical:
                return False

            if self.initialization_mode == CLEAR_PARTITIONS_LINUX and \
               not device.format.linux_native and \
               not device.get_flag(parted.PARTITION_LVM) and \
               not device.get_flag(parted.PARTITION_RAID) and \
               not device.get_flag(parted.PARTITION_SWAP):
                return False
        elif device.is_disk:
            if device.partitioned and self.initialization_mode != CLEAR_PARTITIONS_ALL:
                # if initialization_mode is not CLEAR_PARTITIONS_ALL but we'll still be
                # removing every partition from the disk, return True since we
                # will want to be able to create a new disklabel on this disk
                if not device.is_empty:
                    return False

            # Never clear disks with hidden formats
            if device.format.hidden:
                return False

            # When initialization_mode is CLEAR_PARTITIONS_LINUX and a disk has non-
            # linux whole-disk formatting, do not clear it. The exception is
            # the case of an uninitialized disk when we've been asked to
            # initialize disks as needed
            if (self.initialization_mode == CLEAR_PARTITIONS_LINUX and
                not ((self.initialize_labels and device.is_empty) or
                     (not device.partitioned and device.format.linux_native))):
                return False

        # Don't clear devices holding install media.
        descendants = storage.devicetree.get_dependent_devices(device)
        if device.protected or any(d.protected for d in descendants):
            return False

        if self.initialization_mode == CLEAR_PARTITIONS_LIST and \
           device.device_id not in self.devices_to_clear:
            return False

        return True

    def can_initialize(self, storage, disk):
        """Can the given disk be initialized based on the config?

        :param storage: an instance of the Blivet's storage
        :param disk: an instance of the disk we want to format
        :return: True or False
        """
        log.debug("Can %s be initialized?", disk.name)

        # Skip protected and readonly disks.
        if disk.protected:
            log.debug("A protected disk cannot be initialized.")
            return False

        # Initialize disks with unrecognized formatting.
        if self.format_unrecognized and disk.format.type is None:
            log.debug("A disk with unrecognized formatting can be initialized.")
            return True

        # Initialize disks that were removed.
        if self.can_remove(storage, disk):
            log.debug("The clearable disk can be initialized.")
            return True

        log.debug("The disk cannot be initialized.")
        return False
