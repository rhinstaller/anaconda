import unittest
from unittest.mock import PropertyMock
from unittest.mock import patch
from pykickstart.version import makeVersion
from pyanaconda.storage.kickstart import update_storage_ksdata
from pyanaconda.storage.osinstall import InstallerStorage
from blivet.devices import PartitionDevice
from blivet import formats
from blivet.size import Size


class BlivetTestCase(unittest.TestCase):
    '''
    Define tests for the Blivet class
    '''

    @patch('pyanaconda.dbus.DBus.get_proxy')
    @patch('pyanaconda.storage.osinstall.InstallerStorage.mountpoints', new_callable=PropertyMock)
    def test_prepboot_bootloader_in_kickstart(self, mock_mountpoints, dbus):
        """Test that a prepboot bootloader shows up in the ks data."""
        # disable other partitioning modules
        dbus.return_value.Enabled = False

        # set up prepboot partition
        bootloader_device_obj = PartitionDevice("test_partition_device")
        bootloader_device_obj.size = Size('5 MiB')
        bootloader_device_obj.format = formats.get_format("prepboot")

        # mountpoints must exist for update_ksdata to run
        mock_mountpoints.values.return_value = []

        # set up the storage
        prepboot_blivet_obj = InstallerStorage()
        prepboot_blivet_obj.bootloader.stage1_device = bootloader_device_obj

        # initialize ksdata
        ksdata = makeVersion()
        update_storage_ksdata(prepboot_blivet_obj, ksdata)

        self.assertIn("part prepboot", str(ksdata))

    @patch('pyanaconda.dbus.DBus.get_proxy')
    @patch('pyanaconda.storage.osinstall.InstallerStorage.devices', new_callable=PropertyMock)
    @patch('pyanaconda.storage.osinstall.InstallerStorage.mountpoints', new_callable=PropertyMock)
    def test_biosboot_bootloader_in_kickstart(self, mock_mountpoints, mock_devices, dbus):
        """Test that a biosboot bootloader shows up in the ks data."""
        # disable other partitioning modules
        dbus.return_value.Enabled = False

        # set up biosboot partition
        biosboot_device_obj = PartitionDevice("biosboot_partition_device")
        biosboot_device_obj.size = Size('1MiB')
        biosboot_device_obj.format = formats.get_format("biosboot")

        # mountpoints must exist for updateKSData to run
        mock_devices.return_value = [biosboot_device_obj]
        mock_mountpoints.values.return_value = []

        # initialize ksdata
        ksdata = makeVersion()
        biosboot_blivet_obj = InstallerStorage()
        update_storage_ksdata(biosboot_blivet_obj, ksdata)

        self.assertIn("part biosboot", str(ksdata))
