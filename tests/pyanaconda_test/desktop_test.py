#!/usr/bin/python

import mock
import sys

class DesktopTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])            
        self.fs = mock.DiskIO()
        
        self.fs.open('/tmp/etc/inittab', 'w').write('id:5:initdefault:')
        self.fs.open('/tmp/etc/sysconfig/desktop', 'w').write('')
        
        import pyanaconda.desktop     
        pyanaconda.desktop.log = mock.Mock()
        pyanaconda.desktop.open = self.fs.open
   
    def tearDown(self):
        self.tearDownModules()
        
    def set_default_run_level_1_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        self.assertRaises(RuntimeError, dskt.setDefaultRunLevel, 1)
        self.assertRaises(RuntimeError, dskt.setDefaultRunLevel, 2)
        self.assertRaises(RuntimeError, dskt.setDefaultRunLevel, 4)
        
    def set_default_run_level_2_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultRunLevel(3)
        self.assertEqual(dskt.runlevel, 3)
        dskt.setDefaultRunLevel(5)
        self.assertEqual(dskt.runlevel, 5)
        
    def get_default_run_level_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        self.assertEqual(dskt.getDefaultRunLevel(), dskt.runlevel)
        
    def set_get_default_run_level_1_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultRunLevel(3)
        self.assertEqual(dskt.getDefaultRunLevel(), 3)
        
    def set_get_default_run_level_2_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultRunLevel(5)
        self.assertEqual(dskt.getDefaultRunLevel(), 5)
        
    def set_default_desktop_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultDesktop('desktop')
        self.assertEqual(dskt.info['DESKTOP'], 'desktop')
        
    def get_default_desktop_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.info['DESKTOP'] = 'foobar'
        ret = dskt.getDefaultDesktop()
        self.assertEqual(ret, 'foobar')
        
    def set_get_default_desktop_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultDesktop('foo')
        ret = dskt.getDefaultDesktop()
        self.assertEqual(ret, 'foo')  
        
    def write_1_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()   
        dskt.write('/tmp')
        self.assertEqual(self.fs['/tmp/etc/inittab'], 'id:3:initdefault:')
        
    def write_2_test(self):
        import pyanaconda.desktop
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultRunLevel(5)
        dskt.write('/tmp')
        self.assertEqual(self.fs['/tmp/etc/inittab'], 'id:5:initdefault:')
        
    def write_3_test(self):
        import pyanaconda.desktop
        pyanaconda.desktop.os = mock.Mock()
        pyanaconda.desktop.os.path.isdir.return_value = True
        dskt = pyanaconda.desktop.Desktop()
        dskt.setDefaultDesktop('foo')
        dskt.write('/tmp')
        self.assertEqual(self.fs['/tmp/etc/inittab'], 'id:3:initdefault:')
        self.assertEqual(self.fs['/tmp/etc/sysconfig/desktop'], 'DESKTOP="foo"\n')
        
