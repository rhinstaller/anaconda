#!/usr/bin/python

import mock
import sys

ZONE = 'Europe/Prague'
UTC = 2

class TimeZoneTest(mock.TestCase):
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda.timezone        
        pyanaconda.timezone.log = mock.Mock()
        pyanaconda.timezone.open = self.fs.open
        pyanaconda.timezone.os.access = mock.Mock(return_value = True)
        pyanaconda.timezone.shutil.copyfile = mock.Mock()
        pyanaconda.timezone.os = mock.Mock()
        pyanaconda.timezone.os.access.return_value = True
        pyanaconda.timezone.shutil = mock.Mock()
        #pyanaconda.timezone.shutil.copyfile = mock.Mock()
        
    def tearDown(self):
        self.tearDownModules()
    
    def get_timezone_info_test(self):
        import pyanaconda.timezone        
        tz = pyanaconda.timezone.Timezone()
        info = tz.getTimezoneInfo()        
        self.assertEqual( (tz.tz, tz.utc), info )
        
    def set_timezone_info_test(self):
        import pyanaconda.timezone              
        tz = pyanaconda.timezone.Timezone()
        tz.setTimezoneInfo(ZONE, UTC) 
        self.assertEqual((ZONE, UTC), (tz.tz, tz.utc))       
        
    def write_ks_test(self):
        import pyanaconda.timezone       
        tz = pyanaconda.timezone.Timezone()
        tz.tz = ZONE
        tz.utc = UTC
        
        f = self.fs.open('/test_file', 'w')
        tz.writeKS(f)
        f.close()
        
        example = 'timezone --utc %s\n' % (ZONE)
        self.assertEqual(self.fs['/test_file'], example)
        
    def write_test(self):
        import pyanaconda.timezone
        
        tz = pyanaconda.timezone.Timezone()
        tz.tz = ZONE
        tz.utc = UTC
        
        PATH = ''
        ADJTIME = '0.013782 1279118821 0.000000\n1279118821\nUTC\n'       
        f = self.fs.open('/etc/adjtime', 'w')
        f.write(ADJTIME)
        f.close()      
        
        tz.write(PATH)
        example = 'ZONE="%s"\n' % ZONE
        self.assertEqual(self.fs['/etc/sysconfig/clock'], example)
        self.assertEqual(self.fs['/etc/adjtime'], ADJTIME)
        
        
