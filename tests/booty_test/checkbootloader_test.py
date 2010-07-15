#!/usr/bin/python

import mock

class CheckBootLoaderTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(['_isys', 'block', 'storage', 'parted',
                            'pyanaconda.storage.formats', 'logging', 
                            'ConfigParser', 'pyanaconda.storage.storage_log'])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
        
        import pyanaconda.booty.checkbootloader
        pyanaconda.booty.checkbootloader.iutil = mock.Mock()
        pyanaconda.booty.checkbootloader.os = mock.Mock()
        pyanaconda.booty.checkbootloader.log = mock.Mock()
        pyanaconda.booty.checkbootloader.open = self.fs.open
   
        self.INSTROOT = ''
        self.STORAGE = mock.Mock()
   
    def tearDown(self):
        self.tearDownModules()
        
    def get_boot_dev_string_test(self):
        import pyanaconda.booty.checkbootloader
        LINE = "#boot=/dev/sda"
        ret = pyanaconda.booty.checkbootloader.getBootDevString(LINE)
        self.assertEqual(ret, '/dev/sda')
    
    def get_boot_dev_list_test(self):
        import pyanaconda.booty.checkbootloader
        LINE = "boot=/dev/sda"
        ret = pyanaconda.booty.checkbootloader.getBootDevList(LINE)
        self.assertEqual(ret, '/dev/sda')
        
    def get_bootloader_type_and_boot_grub_1_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return True if 'grub.conf' in path else False
        
        pyanaconda.booty.checkbootloader.os.access = fake_f
        self.fs.open('/etc/sysconfig/grub', 'w').write('boot=/dev/sda\n')
        pyanaconda.booty.checkbootloader.iutil.isEfi = mock.Mock(return_value=True)
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, ('GRUB', '/dev/sda'))
        
    def get_bootloader_type_and_boot_grub_2_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return True if 'grub.conf' in path else False
        
        pyanaconda.booty.checkbootloader.os.access = fake_f
        self.fs.open('/etc/sysconfig/grub', 'w').write('boot=/dev/sda\n')
        pyanaconda.booty.checkbootloader.iutil.isEfi = mock.Mock(return_value=False)
        pyanaconda.booty.checkbootloader.getBootBlock = mock.Mock(return_value=\
            'asdfGRUBasdf')
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, ('GRUB', '/dev/sda'))
        
    def get_bootloader_type_and_boot_lilo_1_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return True if 'lilo.conf' in path else False
        
        pyanaconda.booty.checkbootloader.os.access = fake_f
        self.fs.open('/etc/lilo.conf', 'w').write('boot=/dev/sda\n')
        pyanaconda.booty.checkbootloader.getBootBlock = mock.Mock(return_value=\
            'asdfokLILOasdf')
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, ('LILO', '/dev/sda'))
        
    def get_bootloader_type_and_boot_yaboot_1_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return True if 'yaboot.conf' in path else False
        
        pyanaconda.booty.checkbootloader.os.access = fake_f
        self.fs.open('/etc/yaboot.conf', 'w').write('boot=/dev/sda\n')
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, ('YABOOT', '/dev/sda'))
        
    def get_bootloader_type_and_boot_silo_1_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return True if 'silo.conf' in path else False        
        
        pyanaconda.booty.checkbootloader.os.access = fake_f
        self.fs.open('/etc/sysconfig/silo', 'w').write('boot=/dev/sda\n')
        pyanaconda.booty.checkbootloader.getBootBlock = mock.Mock(return_value=\
            'asdfokasdfghjlasdfghjklaSILOasdf')
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, ('SILO', '/dev/sda'))
        
    def get_bootloader_type_and_boot_none_test(self):
        import pyanaconda.booty.checkbootloader
        
        def fake_f(path, _):
            return False        
            
        pyanaconda.booty.checkbootloader.os.access = fake_f
        
        ret = pyanaconda.booty.checkbootloader.getBootloaderTypeAndBoot(self.INSTROOT, self.STORAGE)
        self.assertEqual(ret, (None, None))
