#!/usr/bin/python

import mock

class BootloaderTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", 'parted', 'storage',
                            'pyanaconda.storage.formats', 'logging', 
                            'ConfigParser', 'pyanaconda.storage.storage_log'])
        
        self.fs = mock.DiskIO()
      
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
        
        import pyanaconda.bootloader
        pyanaconda.bootloader.isys = mock.Mock()
        pyanaconda.bootloader.isys.readFSLabel.return_value = ""
        pyanaconda.bootloader.parted = mock.Mock()
        pyanaconda.bootloader.log = mock.Mock()
        pyanaconda.bootloader.open = self.fs.open
   
    def tearDown(self):
        self.tearDownModules()
        
    def is_efi_system_partition_1_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = "gpt"
        part.name = "EFI System Partition"
        part.getFlag.return_value = True
        part.fileSystem.type = "fat32"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)
        self.assertTrue(ret)
        
    def is_efi_system_partition_2_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = ""
        part.name = "EFI System Partition"
        part.getFlag.return_value = True
        part.fileSystem.type = "fat32"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)
        self.assertFalse(ret)
        
    def is_efi_system_partition_3_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = "gpt"
        part.name = ""
        part.getFlag.return_value = True
        part.fileSystem.type = "fat32"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)
        self.assertFalse(ret)

    def is_efi_system_partition_4_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = "gpt"
        part.name = "EFI System Partition"
        part.getFlag.return_value = False
        part.fileSystem.type = "fat32"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)
        self.assertFalse(ret)  
        
    def is_efi_system_partition_5_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = "gpt"
        part.name = "EFI System Partition"
        part.getFlag.return_value = True
        part.fileSystem.type = "ext4"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)
        self.assertFalse(ret)
        
    def is_efi_system_partition_6_test(self):
        import pyanaconda.bootloader
        part = mock.Mock()
        part.disk.type = "gpt"
        part.name = "EFI System Partition"
        part.getFlag.return_value = True
        part.fileSystem.type = "fat32"
        part.getDeviceNodeName = mock.Mock()
        pyanaconda.bootloader.isys.readFSLabel.return_value = "ANACONDA"
        
        ret = pyanaconda.bootloader.isEfiSystemPartition(part)       
        self.assertFalse(ret)
        
    def bootloader_setup_choices_test(self):
        import pyanaconda.bootloader
        anaconda = mock.Mock()
        anaconda.dir = pyanaconda.bootloader.DISPATCH_FORWARD
        anaconda.bootloader.defaultDevice = 'dev'
        anaconda.platform.bootloaderChoices.return_value = {'dev' : ['']}
        pyanaconda.bootloader.bootloaderSetupChoices(anaconda)
        
        methods = [x[0] for x in anaconda.method_calls]
        self.assertEqual(methods,
            ['bootloader.updateDriveList', 'platform.bootloaderChoices', \
            'dispatch.skipStep', 'bootloader.images.setup', 'bootloader.setDevice']
        )
        
    def fixed_mdraid_grub_target_1_test(self):
        import pyanaconda.bootloader
        pyanaconda.bootloader.getReleaseString = mock.Mock(return_value=('Fedora', '13'))
        anaconda = mock.Mock()
        grubtarget = mock.Mock(return_value='target')
        
        ret = pyanaconda.bootloader.fixedMdraidGrubTarget(anaconda, grubtarget)
        self.assertEqual(ret(), 'target')
        
    def fixed_mdraid_grub_target_2_test(self):
        import pyanaconda.bootloader
        pyanaconda.bootloader.getDiskPart = \
            mock.Mock(return_value=[mock.Mock(return_value='new_target')])
        pyanaconda.bootloader.getReleaseString = mock.Mock(return_value=('Fedora', '10'))
        anaconda = mock.Mock()
        anaconda.bootloader.getPhysicalDevices.return_value = ['']
        grubtarget = mock.Mock(return_value='target')
        
        ret = pyanaconda.bootloader.fixedMdraidGrubTarget(anaconda, grubtarget)
        self.assertEqual(ret(), 'new_target')
        
    def write_bootloader_test(self):
        import pyanaconda.bootloader
        anaconda = mock.Mock()
        anaconda.bootloader.defaultDevice = 1
        anaconda.bootloader.doUpgradeOnly = False
        anaconda.storage.rootDevice = None
        anaconda.rootPath = ''
        anaconda.bootloader.images.getDefault.return_value = False
        anaconda.bootloader.images.getImages().items.return_value = \
            [('/dev/sda1', ('label', 'long_label', None))]
        anaconda.backend.kernelVersionList.return_value = \
            [('2.6.33.5-124', 'i386', 'base')]
        anaconda.bootloader.write.return_value = 0
        
        pyanaconda.bootloader.writeBootloader(anaconda)
        self.assertEqual(self.fs['/etc/sysconfig/kernel'],
            '# UPDATEDEFAULT specifies if new-kernel-pkg should make\n'
            '# new kernels the default\nUPDATEDEFAULT=yes\n\n'
            '# DEFAULTKERNEL specifies the default kernel package type\n'
            'DEFAULTKERNEL=kernel\n'
        )
        
        try:
            arg = anaconda.bootloader.write.call_args_list[0][0][2]
        except:
            arg = None
        self.assertEqual(arg, [('label', 'long_label', '2.6.33.5-124')])
        
    def has_windows_1_test(self):
        import pyanaconda.bootloader
        pyanaconda.bootloader.booty.doesDualBoot = mock.Mock(return_value=False)
        bl = mock.Mock()
        ret = pyanaconda.bootloader.hasWindows(bl)
        self.assertFalse(ret)
        
    def has_windows_2_test(self):
        import pyanaconda.bootloader
        pyanaconda.bootloader.booty.doesDualBoot = mock.Mock(return_value=True)
        bl = mock.Mock()
        bl.images.availableBootDevices.return_value = []
        ret = pyanaconda.bootloader.hasWindows(bl)
        self.assertFalse(ret)
        
    def has_windows_3_test(self):
        import pyanaconda.bootloader
        pyanaconda.bootloader.booty.doesDualBoot = mock.Mock(return_value=True)
        pyanaconda.bootloader.booty.dosFileSystems = mock.Mock(return_value=True)
        bl = mock.Mock()
        bl.images.availableBootDevices.return_value = [('', 'fat32')]
        ret = pyanaconda.bootloader.hasWindows(bl)
        self.assertTrue(ret)
        
