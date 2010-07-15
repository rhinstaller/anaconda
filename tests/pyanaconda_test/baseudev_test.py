#!/usr/bin/python

import mock
import os

class BaseudevTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])
        self.fs = mock.DiskIO()
        
        import pyanaconda.baseudev
        pyanaconda.baseudev.os = mock.Mock()
        pyanaconda.baseudev.log = mock.Mock()
        pyanaconda.baseudev.open = self.fs.open
        
    def tearDown(self):
        self.tearDownModules()
        
    def udev_enumerate_devices_test(self):
        import pyanaconda.baseudev      
        ENUMERATE_LIST = [
            '/sys/devices/pci0000:00/0000:00:1f.2/host0/target0:0:0/0:0:0:0/block/sda', 
            '/sys/devices/virtual/block/loop0', 
            '/sys/devices/virtual/block/loop1', 
            '/sys/devices/virtual/block/ram0', 
            '/sys/devices/virtual/block/ram1', 
            '/sys/devices/virtual/block/dm-0',
        ]
        
        pyanaconda.baseudev.global_udev.enumerate_devices = mock.Mock(return_value=ENUMERATE_LIST)
        ret = pyanaconda.baseudev.udev_enumerate_devices()
        self.assertEqual(set(ret), 
            set(['/devices/pci0000:00/0000:00:1f.2/host0/target0:0:0/0:0:0:0/block/sda', 
            '/devices/virtual/block/loop0', '/devices/virtual/block/loop1', 
            '/devices/virtual/block/ram0', '/devices/virtual/block/ram1', 
            '/devices/virtual/block/dm-0'])
        )
        
    def udev_get_device_1_test(self):
        import pyanaconda.baseudev
        
        class Device(object):
            def __init__(self):
                self.sysname = 'loop1'
                self.dict = {'symlinks': ['/dev/block/7:1'],
                    'SUBSYSTEM': 'block', 
                    'MAJOR': '7', 
                    'DEVPATH': '/devices/virtual/block/loop1', 
                    'UDISKS_PRESENTATION_NOPOLICY': '1', 
                    'UDEV_LOG': '3', 
                    'DEVNAME': '/dev/loop1', 
                    'DEVTYPE': 'disk', 
                    'DEVLINKS': '/dev/block/7:1', 
                    'MINOR': '1'
                }
                
            def __getitem__(self, key):
                return self.dict[key]
                
            def __setitem__(self, key, value):
                self.dict[key] = value
        
        pyanaconda.baseudev.os.path.exists.return_value = True
        DEV_PATH = '/devices/virtual/block/loop1'
        dev = Device()
        pyanaconda.baseudev.global_udev = mock.Mock()
        pyanaconda.baseudev.global_udev.create_device.return_value = dev
        pyanaconda.baseudev.udev_parse_uevent_file = mock.Mock(return_value=dev)
        
        ret = pyanaconda.baseudev.udev_get_device(DEV_PATH)
        self.assertTrue(isinstance(ret, Device))
        self.assertEqual(ret['name'], ret.sysname)
        self.assertEqual(ret['sysfs_path'], DEV_PATH)
        self.assertTrue(pyanaconda.baseudev.udev_parse_uevent_file.called)

    def udev_get_device_2_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.os.path.exists.return_value = False
        ret = pyanaconda.baseudev.udev_get_device('')
        self.assertEqual(ret, None)

    def udev_get_device_3_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.os.path.exists.return_value = True
        pyanaconda.baseudev.global_udev = mock.Mock()
        pyanaconda.baseudev.global_udev.create_device.return_value = None
        ret = pyanaconda.baseudev.udev_get_device('')
        self.assertEqual(ret, None)
    
    def udev_get_devices_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.udev_settle = mock.Mock()
        DEVS = \
            ['/devices/pci0000:00/0000:00:1f.2/host0/target0:0:0/0:0:0:0/block/sda', 
            '/devices/virtual/block/loop0', '/devices/virtual/block/loop1', 
            '/devices/virtual/block/ram0', '/devices/virtual/block/ram1', 
            '/devices/virtual/block/dm-0']
        pyanaconda.baseudev.udev_enumerate_devices = mock.Mock(return_value=DEVS)
        pyanaconda.baseudev.udev_get_device = lambda x: x
        ret = pyanaconda.baseudev.udev_get_devices()
        self.assertEqual(ret, DEVS)
            
    def udev_parse_uevent_file_1_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.os.path.normpath = os.path.normpath
        pyanaconda.baseudev.os.access.return_value = True
        
        FILE_CONTENT = "MAJOR=7\nMINOR=1\nDEVNAME=loop1\nDEVTYPE=disk\n"
        self.fs.open('/sys/devices/virtual/block/loop1/uevent', 'w').write(FILE_CONTENT)
        dev = {'sysfs_path': '/devices/virtual/block/loop1'}
        ret = pyanaconda.baseudev.udev_parse_uevent_file(dev)
        self.assertEqual(ret,
            {'sysfs_path': '/devices/virtual/block/loop1', 
            'DEVNAME': 'loop1',
            'DEVTYPE': 'disk',
            'MAJOR': '7',
            'MINOR': '1'})
                   
    def udev_parse_uevent_file_2_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.os.path.normpath = os.path.normpath
        pyanaconda.baseudev.os.access.return_value = False
        
        dev = {'sysfs_path': '/devices/virtual/block/loop1'}
        ret = pyanaconda.baseudev.udev_parse_uevent_file(dev)
        self.assertEqual(ret, {'sysfs_path': '/devices/virtual/block/loop1'})
   
    def udev_settle_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.iutil = mock.Mock()
        pyanaconda.baseudev.udev_settle()
        self.assertTrue(pyanaconda.baseudev.iutil.execWithRedirect.called)
             
    def udev_trigger_test(self):
        import pyanaconda.baseudev
        pyanaconda.baseudev.iutil = mock.Mock()
        pyanaconda.baseudev.udev_trigger()
        self.assertTrue(pyanaconda.baseudev.iutil.execWithRedirect.called)
        
