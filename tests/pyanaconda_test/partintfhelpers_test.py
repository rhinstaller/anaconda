#!/usr/bin/python

import mock

class PartIntfHelpersTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", 'parted', 'storage',
                            'pyanaconda.storage.formats', 'logging',
                            'ConfigParser', 'pyanaconda.storage.storage_log'])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
        
        import pyanaconda.partIntfHelpers
          
    def tearDown(self):
        self.tearDownModules()

    # sanityCheckVolumeGroupName tests

    def sanitycheckvolumegroupname_right_hostname_1_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = "hostname"
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertEqual(ret, None)
    
    def sanitycheckvolumegroupname_right_hostname_2_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = "h"
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertEqual(ret, None)
    
    def sanitycheckvolumegroupname_right_hostname_3_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = "a" * 127
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertEqual(ret, None)
    
    def sanitycheckvolumegroupname_right_hostname_4_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = "h-o_s-t.name"
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertEqual(ret, None)
    
    def sanitycheckvolumegroupname_empty_hostname_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = ""
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_long_hostname_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = "asdfasdfas" * 13
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_1_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = 'lvm'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_2_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = 'root'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_3_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = '.'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_4_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = '..'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_5_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = 'foo bar'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    def sanitycheckvolumegroupname_bad_hostname_6_test(self):
        import pyanaconda.partIntfHelpers
        HOSTNAME = 'foob@r'
        ret = pyanaconda.partIntfHelpers.sanityCheckVolumeGroupName(HOSTNAME)
        self.assertNotEqual(ret, None)
    
    # sanityCheckLogicalVolumeName test
    
    def sanitychecklogicalvolumename_right_name_1_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "name"
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertEqual(ret, None)
    
    def sanitychecklogicalvolumename_right_name_2_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "name_00.9"
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertEqual(ret, None)
    
    def sanitychecklogicalvolumename_right_name_3_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "a"
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertEqual(ret, None)
    
    def sanitychecklogicalvolumename_empty_name_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = ""
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_long_name_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "b" * 129
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_bad_name_1_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "group"
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_bad_name_2_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = "."
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_bad_name_3_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = ".."
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_bad_name_4_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = 'foo bar'
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    def sanitychecklogicalvolumename_bad_name_5_test(self):
        import pyanaconda.partIntfHelpers
        LOGVOLNAME = 'foob@r'
        ret = pyanaconda.partIntfHelpers.sanityCheckLogicalVolumeName(LOGVOLNAME)
        self.assertNotEqual(ret, None)
    
    # sanityCheckMountPoint test
    
    def sanitycheckmountpoint_right_name_1_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/foob@r'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertEqual(ret, None)
    
    def sanitycheckmountpoint_right_name_2_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/var'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertEqual(ret, None)
    
    def sanitycheckmountpoint_right_name_3_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertEqual(ret, None)
    
    def sanitycheckmountpoint_bad_name_1_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '//'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
        
    def sanitycheckmountpoint_bad_name_2_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/foo bar'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
    
    def sanitycheckmountpoint_bad_name_3_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/./'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
    
    def sanitycheckmountpoint_bad_name_4_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/../'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
    
    def sanitycheckmountpoint_bad_name_5_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/..'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
    
    def sanitycheckmountpoint_bad_name_6_test(self):
        import pyanaconda.partIntfHelpers
        MNTPT = '/.'
        ret = pyanaconda.partIntfHelpers.sanityCheckMountPoint(MNTPT)
        self.assertNotEqual(ret, None)
    
    def dodeletedevice_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        STORAGE = mock.Mock()
        DEVICE = None
        ret = pyanaconda.partIntfHelpers.doDeleteDevice(INTF, STORAGE, DEVICE)
        self.assertFalse(ret)
    
    def dodeletedevice_2_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        STORAGE = mock.Mock()
        STORAGE.deviceImmutable.return_value = True
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doDeleteDevice(INTF, STORAGE, DEVICE)
        self.assertFalse(ret)
    
    def dodeletedevice_3_test(self):
        import pyanaconda.partIntfHelpers
        pyanaconda.partIntfHelpers.confirmDelete = mock.Mock(return_value=False)
        INTF = mock.Mock()
        STORAGE = mock.Mock()
        STORAGE.deviceImmutable.return_value = False
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doDeleteDevice(INTF, STORAGE, DEVICE)
        self.assertFalse(ret)
    
    def dodeletedevice_4_test(self):
        import pyanaconda.partIntfHelpers
        pyanaconda.partIntfHelpers.confirmDelete = mock.Mock(return_value=False)
        INTF = mock.Mock()
        STORAGE = mock.Mock()
        STORAGE.deviceImmutable.return_value = False
        STORAGE.deviceDeps.return_value = []
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doDeleteDevice(INTF, STORAGE, DEVICE,
                                                        confirm=0)
        self.assertTrue(ret)
        self.assertTrue(STORAGE.destroyDevice.called)
    
    def dodeletedevice_5_test(self):
        import pyanaconda.partIntfHelpers
        pyanaconda.partIntfHelpers.confirmDelete = mock.Mock(return_value=True)
        INTF = mock.Mock()
        STORAGE = mock.Mock()
        STORAGE.deviceImmutable.return_value = False
        STORAGE.deviceDeps.return_value = []
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doDeleteDevice(INTF, STORAGE, DEVICE)
        self.assertTrue(ret)
        self.assertTrue(STORAGE.destroyDevice.called)
    
    def doclearpartitioneddevice_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        INTF.messageWindow.return_value = 0
        STORAGE = mock.Mock()
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doClearPartitionedDevice(INTF, STORAGE,
                                                                  DEVICE)
        self.assertFalse(ret)
    
    def doclearpartitioneddevice_2_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        INTF.messageWindow.return_value = 1
        STORAGE = mock.Mock()
        STORAGE.partitions = []
        DEVICE = mock.Mock()
        ret = pyanaconda.partIntfHelpers.doClearPartitionedDevice(INTF, STORAGE,
                                                                  DEVICE)
        self.assertFalse(ret)
    
    def doclearpartitioneddevice_3_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        INTF.messageWindow.return_value = 1
        DEVICE = mock.Mock()
        p = mock.Mock()
        p.disk = DEVICE
        p.partedPartition.number = 0
        STORAGE = mock.Mock()
        STORAGE.partitions = [p]
        STORAGE.deviceImmutable.return_value = False
        STORAGE.deviceDeps.return_value = []
        
        ret = pyanaconda.partIntfHelpers.doClearPartitionedDevice(INTF, STORAGE,
                                                                  DEVICE)
        self.assertTrue(ret)
    
    def checkforswapnomatch_test(self):
        import pyanaconda.partIntfHelpers
        pyanaconda.partIntfHelpers.parted.PARTITION_SWAP = 5
        device = mock.Mock()
        device.exists.return_value = True
        device.getFlag.return_value = True
        device.format.type == "swap"
        ANACONDA = mock.Mock()
        ANACONDA.storage.partitions = [device]
        ANACONDA.intf.messageWindow.return_value = 1
        pyanaconda.partIntfHelpers.checkForSwapNoMatch(ANACONDA)
        self.assertTrue(ANACONDA.storage.formatDevice.called)
    
    def musthaveselecteddrive_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        pyanaconda.partIntfHelpers.mustHaveSelectedDrive(INTF)
        self.assertTrue(INTF.messageWindow.called)
    
    def querynoformatpreexisting_test(self):
        import pyanaconda.partIntfHelpers
        RET = 22
        INTF = mock.Mock()
        ret = INTF.messageWindow.return_value = RET
        self.assertEqual(RET, ret)
    
    def partitionsanityerrors_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        ERRORS = []
        ret = pyanaconda.partIntfHelpers.partitionSanityErrors(INTF, ERRORS)
        self.assertEqual(1, ret)
    
    def partitionsanityerrors_2_test(self):
        import pyanaconda.partIntfHelpers
        RET = 5
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        ERRORS = ['err string', 'foo string']
        ret = pyanaconda.partIntfHelpers.partitionSanityErrors(INTF, ERRORS)
        self.assertEqual(RET, ret)
        self.assertTrue(ERRORS[0] in INTF.messageWindow.call_args[0][1])
        self.assertTrue(ERRORS[1] in INTF.messageWindow.call_args[0][1])
    
    def partitionsanitywarnings_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        WARNINGS = []
        ret = pyanaconda.partIntfHelpers.partitionSanityWarnings(INTF, WARNINGS)
        self.assertEqual(1, ret)
    
    def partitionsanitywarnings_2_test(self):
        import pyanaconda.partIntfHelpers
        RET = 5
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        WARNINGS = ['warning string', 'foo string']
        ret = pyanaconda.partIntfHelpers.partitionSanityWarnings(INTF, WARNINGS)
        self.assertEqual(RET, ret)
        self.assertTrue(WARNINGS[0] in INTF.messageWindow.call_args[0][1])
        self.assertTrue(WARNINGS[1] in INTF.messageWindow.call_args[0][1])
    
    def partitionpreexistformatwarnings_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        WARNINGS = []
        ret = pyanaconda.partIntfHelpers.partitionPreExistFormatWarnings(INTF, WARNINGS)
        self.assertEqual(1, ret)
    
    def partitionpreexistformatwarnings_2_test(self):
        import pyanaconda.partIntfHelpers
        RET = 10
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        WARNINGS = [('foo', 'foobar', '/foodir')]
        ret = pyanaconda.partIntfHelpers.partitionPreExistFormatWarnings(INTF, WARNINGS)
        self.assertEqual(RET, ret)
        self.assertTrue(WARNINGS[0][0] in INTF.messageWindow.call_args[0][1])
    
    def getpreexistformatwarnings_1_test(self):
        import pyanaconda.partIntfHelpers
        STORAGE = mock.Mock()
        STORAGE.devicetree.devices = []
        ret = pyanaconda.partIntfHelpers.getPreExistFormatWarnings(STORAGE)
        self.assertEqual([], ret)
    
    def getpreexistformatwarnings_2_test(self):
        import pyanaconda.partIntfHelpers
        STORAGE = mock.Mock()
        device = mock.Mock()
        device.exists = True
        device.name = 'foodev'
        device.path = '/foodevdir'
        device.format.name = 'fffoodev'
        device.format.mountpoint = '/mnt/foo'
        device.format.exists = False
        device.format.hidden = False
        STORAGE.devicetree.devices = [device]
        ret = pyanaconda.partIntfHelpers.getPreExistFormatWarnings(STORAGE)
        self.assertEqual([('/foodevdir', 'fffoodev', '/mnt/foo')], ret)
    
    def confirmdelete_1_test(self):
        import pyanaconda.partIntfHelpers
        INTF = mock.Mock()
        DEVICE = False
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(None, ret)
    
    def confirmdelete_2_test(self):
        import pyanaconda.partIntfHelpers
        RET = 51
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        DEVICE = mock.Mock()
        DEVICE.type = "lvmvg"
        DEVICE.name = "devname"
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(RET, ret)
        self.assertTrue(DEVICE.name in INTF.messageWindow.call_args[0][1])
    
    def confirmdelete_3_test(self):
        import pyanaconda.partIntfHelpers
        RET = 52
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        DEVICE = mock.Mock()
        DEVICE.type = "lvmlv"
        DEVICE.name = "devname"
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(RET, ret)
        self.assertTrue(DEVICE.name in INTF.messageWindow.call_args[0][1])
    
    def confirmdelete_4_test(self):
        import pyanaconda.partIntfHelpers
        RET = 53
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        DEVICE = mock.Mock()
        DEVICE.type = "mdarray"
        DEVICE.name = "devname"
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(RET, ret)
    
    def confirmdelete_5_test(self):
        import pyanaconda.partIntfHelpers
        RET = 54
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        DEVICE = mock.Mock()
        DEVICE.type = "partition"
        DEVICE.name = "devname"
        DEVICE.path = "/dev/devname"
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(RET, ret)
        self.assertTrue(DEVICE.path in INTF.messageWindow.call_args[0][1])
    
    def confirmdelete_6_test(self):
        import pyanaconda.partIntfHelpers
        RET = 55
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        DEVICE = mock.Mock()
        DEVICE.type = "other"
        DEVICE.name = "devname"
        ret = pyanaconda.partIntfHelpers.confirmDelete(INTF, DEVICE)
        self.assertEqual(RET, ret)
        self.assertTrue(DEVICE.type in INTF.messageWindow.call_args[0][1])
        self.assertTrue(DEVICE.name in INTF.messageWindow.call_args[0][1])
    
    def confirmresetpartitionstate_test(self):
        import pyanaconda.partIntfHelpers
        RET = 61
        INTF = mock.Mock()
        INTF.messageWindow.return_value = RET
        ret = pyanaconda.partIntfHelpers.confirmResetPartitionState(INTF)
        self.assertEqual(RET, ret)
    
