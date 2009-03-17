#! /usr/bin/env python
# -*- coding: utf8 -*-

import unittest
import storage.devicetree as devicetree
import storage.devices as devices

from storage.udev import udev_get_block_devices, udev_device_get_sysfs_path
from tests.storage.devicelibs.baseclass import makeLoopDev, removeLoopDev


class DeviceTreeTestCase(unittest.TestCase):
    """
    Device tree test case
    """
    _LOOP_DEV = "/dev/loop0"
    _LOOP_FILE = "/tmp/loop0"

    def setUp(self):
        print "Creating the loop dev"
        for loop_dev, loop_file in [(self._LOOP_DEV, self._LOOP_FILE)]:
            makeLoopDev(loop_dev, loop_file)

        print "Creating the device tree"
        self.dt = devicetree.DeviceTree()
        print "Populating"
        self.dt.populate()

    def tearDown(self):
        print "Destroying the device tree"
        del self.dt

        print "Removing the loop dev"
        for loop_dev, loop_file in [(self._LOOP_DEV, self._LOOP_FILE)]:
            removeLoopDev(loop_dev, loop_file)

    def runTest(self):
        print "\nDevices:"
        for path, device in self.dt.devices.items():
            print path, device.name
            # check if we get the right device from name
            self.assertEqual(self.dt.getDeviceByName(device.name).name, device.name)

            print "\tChildren:"
            for child in self.dt.getChildren(device):
                print "\t%s" % child.name

        # see if everything goes ok
        self.assertEqual(self.dt.setupAll(), None)

        # we have no actions registered
        self.assertEqual(self.dt.findActions(), [])

        # shouldn't do anything, but see if it does not fail
        self.assertEqual(self.dt.pruneActions(), None)
        self.assertEqual(self.dt.processActions(), None)

        print "\nFilesystems:"
        for filesystem in self.dt.filesystems:
            print filesystem

        print "\nUUIDs:"
        for uuid, device in self.dt.uuids.items():
            print uuid, device.name
            # check if we get the right device from uuid
            self.assertEqual(self.dt.getDeviceByUuid(uuid).name, device.name)

        print "\nLabels:"
        for label, device in self.dt.labels.items():
            print label, device.name
            # check if we get the right device from label
            self.assertEqual(self.dt.getDeviceByLabel(label).name, device.name)

        print "\nLeaves:"
        for leaf in self.dt.leaves:
            print leaf.name

            print "\tDependent devices:"
            for device in self.dt.getDependentDevices(leaf):
                print "\t%s" % device.name

        block_devices = udev_get_block_devices()
        # is the loop device ignored?
        for udev_device in block_devices:
            if udev_device['name'].find(self._LOOP_DEV) != -1:
                self.assertEqual(self.dt.isIgnored(udev_device), True)

        # check if we get the right device from sysfs path
        for udev_device in block_devices:
            sysfs_path = udev_device_get_sysfs_path(udev_device)
            self.assertEqual(self.dt.getDeviceBySysfsPath(sysfs_path).name, udev_device['name'])

        print "\nDisk devices:"
        for device in self.dt.getDevicesByType("disk"):
            print device.name
            # check if the returned device is the expected instance
            self.assertEqual(isinstance(device, devices.DiskDevice), True)

            # get udev dict for this device
            udev_info = None
            for udev_device in block_devices:
                if udev_device['name'] == device.name:
                    udev_info = udev_device
                    break

            if udev_info:
                # check if ignoring device works
                self.assertEqual(self.dt.isIgnored(udev_info), None)    # not False
                self.dt.addIgnoredDisk(device.name)
                self.assertEqual(self.dt.isIgnored(udev_info), True)

        print "\nPartition devices:"
        # check if we get the right devices of a particular instance
        for device in self.dt.getDevicesByInstance(devices.PartitionDevice):
            print device.name
            # check if the returned device is the expected instance
            self.assertEqual(isinstance(device, devices.PartitionDevice), True)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DeviceTreeTestCase)


if __name__ == "__main__":
    unittest.main()
