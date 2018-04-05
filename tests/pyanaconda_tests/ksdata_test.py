import unittest
from unittest.mock import PropertyMock
from unittest.mock import patch
from pykickstart.version import F28, makeVersion
from pyanaconda.storage.osinstall import InstallerStorage
from blivet.devices import PartitionDevice
from blivet import formats
from blivet.size import Size


class BlivetTestCase(unittest.TestCase):
    '''
    Define tests for the Blivet class
    '''
    @patch('pyanaconda.dbus.DBus.get_proxy')
    @patch('pyanaconda.storage.osinstall.InstallerStorage.bootloader_device', new_callable=PropertyMock)
    @patch('pyanaconda.storage.osinstall.InstallerStorage.mountpoints', new_callable=PropertyMock)
    def test_prepboot_bootloader_in_kickstart(self, mock_mountpoints, mock_bootloader_device, dbus):
        """Test that a prepboot bootloader shows up in the ks data."""
        # set up prepboot partition
        bootloader_device_obj = PartitionDevice("test_partition_device")
        bootloader_device_obj.size = Size('5 MiB')
        bootloader_device_obj.format = formats.get_format("prepboot")

        # mountpoints must exist for update_ksdata to run
        mock_bootloader_device.return_value = bootloader_device_obj
        mock_mountpoints.values.return_value = []

        # initialize ksdata
        prepboot_blivet_obj = InstallerStorage(makeVersion(F28))
        prepboot_blivet_obj.update_ksdata()

        self.assertIn("part prepboot", str(prepboot_blivet_obj.ksdata))

    @patch('pyanaconda.dbus.DBus.get_proxy')
    @patch('pyanaconda.storage.osinstall.InstallerStorage.devices', new_callable=PropertyMock)
    @patch('pyanaconda.storage.osinstall.InstallerStorage.mountpoints', new_callable=PropertyMock)
    def test_biosboot_bootloader_in_kickstart(self, mock_mountpoints, mock_devices, dbus):
        """Test that a biosboot bootloader shows up in the ks data."""
        # set up biosboot partition
        biosboot_device_obj = PartitionDevice("biosboot_partition_device")
        biosboot_device_obj.size = Size('1MiB')
        biosboot_device_obj.format = formats.get_format("biosboot")

        # mountpoints must exist for updateKSData to run
        mock_devices.return_value = [biosboot_device_obj]
        mock_mountpoints.values.return_value = []

        # initialize ksdata
        biosboot_blivet_obj = InstallerStorage(makeVersion())
        biosboot_blivet_obj.update_ksdata()

        self.assertIn("part biosboot", str(biosboot_blivet_obj.ksdata))
