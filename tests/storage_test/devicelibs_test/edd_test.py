import mock

class EddTestCase(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'pyanaconda.anaconda_log', 'block'])

    def tearDown(self):
        from pyanaconda.storage.devicelibs import edd
        self.tearDownModules()
        mock.DiskIO.restore_module(edd)

    def test_biosdev_to_edd_dir(self):
        from pyanaconda.storage.devicelibs import edd
        path = edd.biosdev_to_edd_dir(138)
        self.assertEqual("/sys/firmware/edd/int13_dev8a", path)

    def test_collect_edd_data(self):
        from pyanaconda.storage.devicelibs import edd

        # test with vda, vdb
        fs = EddTestFS(edd).vda_vdb()
        edd_dict = edd.collect_edd_data()
        self.assertEqual(len(edd_dict), 2)
        self.assertEqual(edd_dict[0x80].type, "SCSI")
        self.assertEqual(edd_dict[0x80].scsi_id, 0)
        self.assertEqual(edd_dict[0x80].scsi_lun, 0)
        self.assertEqual(edd_dict[0x80].pci_dev, "00:05.0")
        self.assertEqual(edd_dict[0x80].channel, 0)
        self.assertEqual(edd_dict[0x80].sectors, 16777216)
        self.assertEqual(edd_dict[0x81].pci_dev, "00:06.0")

        # test with sda, vda
        fs = EddTestFS(edd).sda_vda()
        edd_dict = edd.collect_edd_data()
        self.assertEqual(len(edd_dict), 2)
        self.assertEqual(edd_dict[0x80].type, "ATA")
        self.assertEqual(edd_dict[0x80].scsi_id, None)
        self.assertEqual(edd_dict[0x80].scsi_lun, None)
        self.assertEqual(edd_dict[0x80].pci_dev, "00:01.1")
        self.assertEqual(edd_dict[0x80].channel, 0)
        self.assertEqual(edd_dict[0x80].sectors, 2097152)
        self.assertEqual(edd_dict[0x80].ata_device, 0)
        self.assertEqual(edd_dict[0x80].mbr_signature, "0x000ccb01")

    def test_edd_entry_str(self):
        from pyanaconda.storage.devicelibs import edd
        fs = EddTestFS(edd).sda_vda()
        edd_dict = edd.collect_edd_data()
        expected_output = """\ttype: ATA, ata_device: 0
\tchannel: 0, mbr_signature: 0x000ccb01
\tpci_dev: 00:01.1, scsi_id: None
\tscsi_lun: None, sectors: 2097152"""
        self.assertEqual(str(edd_dict[0x80]), expected_output)

    def test_matcher_device_path(self):
        from pyanaconda.storage.devicelibs import edd
        fs = EddTestFS(edd).sda_vda()
        edd_dict = edd.collect_edd_data()

        analyzer = edd.EddMatcher(edd_dict[0x80])
        path = analyzer.devname_from_pci_dev()
        self.assertEqual(path, "sda")

        analyzer = edd.EddMatcher(edd_dict[0x81])
        path = analyzer.devname_from_pci_dev()
        self.assertEqual(path, "vda")

    def test_get_edd_dict_1(self):
        """ Test get_edd_dict()'s pci_dev matching. """
        from pyanaconda.storage.devicelibs import edd
        fs = EddTestFS(edd).sda_vda()
        self.assertEqual(edd.get_edd_dict([]),
                         {'sda' : 0x80,
                          'vda' : 0x81})

    def test_get_edd_dict_2(self):
        """ Test get_edd_dict()'s pci_dev matching. """
        from pyanaconda.storage.devicelibs import edd
        edd.collect_mbrs = mock.Mock(return_value = {
                'sda' : '0x000ccb01',
                'vda' : '0x0006aef1'})
        fs = EddTestFS(edd).sda_vda_missing_details()
        self.assertEqual(edd.get_edd_dict([]),
                         {'sda' : 0x80,
                          'vda' : 0x81})



class EddTestFS(object):
    def __init__(self, target_module):
        self.fs = mock.DiskIO()
        self.fs.take_over_module(target_module)

    def sda_vda_missing_details(self):
        self.fs["/sys/firmware/edd/int13_dev80"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev80/mbr_signature"] = "0x000ccb01"
        self.fs["/sys/firmware/edd/int13_dev81"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev81/mbr_signature"] = "0x0006aef1"

    def sda_vda(self):
        self.fs["/sys/firmware/edd/int13_dev80"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev80/host_bus"] = "PCI 	00:01.1  channel: 0\n"
        self.fs["/sys/firmware/edd/int13_dev80/interface"] = "ATA     	device: 0\n"
        self.fs["/sys/firmware/edd/int13_dev80/mbr_signature"] = "0x000ccb01"
        self.fs["/sys/firmware/edd/int13_dev80/sectors"] = "2097152\n"

        self.fs["/sys/firmware/edd/int13_dev81"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev81/host_bus"] = "PCI 	00:05.0  channel: 0\n"
        self.fs["/sys/firmware/edd/int13_dev81/interface"] = "SCSI    	id: 0  lun: 0\n"
        self.fs["/sys/firmware/edd/int13_dev81/mbr_signature"] = "0x0006aef1"
        self.fs["/sys/firmware/edd/int13_dev81/sectors"] = "16777216\n"

        self.fs["/sys/devices/pci0000:00/0000:00:01.1/host0/target0:0:0/0:0:0:0/block"] = self.fs.Dir()
        self.fs["/sys/devices/pci0000:00/0000:00:01.1/host0/target0:0:0/0:0:0:0/block/sda"] = self.fs.Dir()

        self.fs["/sys/devices/pci0000:00/0000:00:05.0/virtio2/block"] = self.fs.Dir()
        self.fs["/sys/devices/pci0000:00/0000:00:05.0/virtio2/block/vda"] = self.fs.Dir()

        return self.fs

    def vda_vdb(self):
        self.fs["/sys/firmware/edd/int13_dev80"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev80/host_bus"] = "PCI 	00:05.0  channel: 0\n"
        self.fs["/sys/firmware/edd/int13_dev80/interface"] = "SCSI    	id: 0  lun: 0\n"
        self.fs["/sys/firmware/edd/int13_dev80/sectors"] = "16777216\n"

        self.fs["/sys/firmware/edd/int13_dev81"] = self.fs.Dir()
        self.fs["/sys/firmware/edd/int13_dev81/host_bus"] = "PCI 	00:06.0  channel: 0\n"
        self.fs["/sys/firmware/edd/int13_dev81/interface"] = "SCSI    	id: 0  lun: 0\n"
        self.fs["/sys/firmware/edd/int13_dev81/sectors"] = "4194304\n"

        return self.fs
