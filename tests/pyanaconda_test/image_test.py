#!/usr/bin/python

import mock
import sys

IMAGENAME = 'Fedora-13-i386-DVD.iso'

class ImageTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])            
        self.fs = mock.DiskIO()
        
        DISCINFO = "1273712438.740122\n"
        DISCINFO += "Fedora 13\n"
        DISCINFO += "i386\n"
        DISCINFO += "ALL\n"

        DISCINFO2 = "1273712438.740122\n"
        DISCINFO2 += "Fedora 13\n"
        DISCINFO2 += "i386\n"
        DISCINFO2 += "1,2\n"
        
        self.fs.open('/mnt/cdimage/.discinfo', 'w').write(DISCINFO)
        self.fs.open('/tmp/.discinfo', 'w').write(DISCINFO2)
        
        import pyanaconda.image     
        pyanaconda.image.gettext = mock.Mock()  
        pyanaconda.image.log = mock.Mock()    
        pyanaconda.image.open = self.fs.open
        pyanaconda.image.isys = mock.Mock()
        pyanaconda.image._arch = 'i386'
        pyanaconda.image.stat = mock.Mock()
        pyanaconda.image.stat.ST_SIZE = 0
        
        pyanaconda.image.os = mock.Mock()
        pyanaconda.image.os.R_OK = 0
        pyanaconda.image.os.stat.return_value = [2048]
        pyanaconda.image.os.listdir.return_value=[IMAGENAME]
    
    def tearDown(self):
        self.tearDownModules()
        
    def find_iso_images_1_test(self):
        import pyanaconda.image
        
        pyanaconda.image.getDiscNums = mock.Mock(return_value=[1])
        ret = pyanaconda.image.findIsoImages('', mock.Mock())
        
        self.assertEqual(ret, {1: IMAGENAME})
        
        self.assertEqual(pyanaconda.image.isys.method_calls, 
            [('isIsoImage', ('/Fedora-13-i386-DVD.iso',), {}), 
             ('mount', ('/Fedora-13-i386-DVD.iso', '/mnt/cdimage'), 
                                    {'readOnly': True, 'fstype': 'iso9660'}), 
             ('umount', ('/mnt/cdimage',), {'removeDir': False})]
        )
    
    def find_iso_images_2_test(self):
        import pyanaconda.image
        pyanaconda.image.isys.mount = mock.Mock(side_effect=SystemError())
        ret = pyanaconda.image.findIsoImages('', mock.Mock())
        
        self.assertEqual(ret, {})
        
        self.assertEqual(pyanaconda.image.isys.method_calls, 
            [('isIsoImage', ('/Fedora-13-i386-DVD.iso',), {})]
        )
        
    def get_disc_nums_1_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.getDiscNums('ALL')
        self.assertEqual(ret, [1])
        
    def get_disc_nums_2_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.getDiscNums('1, 2, 3, 4')
        self.assertEqual(ret, [1, 2, 3, 4])
        
    def get_disc_nums_3_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.getDiscNums('1,2,3')
        self.assertEqual(ret, [1, 2, 3])
        
    def get_media_id_1_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.getMediaId('/mnt/cdimage')
        self.assertEqual(ret, '1273712438.740122') 
        
    def get_media_id_2_test(self):         
        import pyanaconda.image
        pyanaconda.image.os.access = mock.Mock(return_value=False)
        ret = pyanaconda.image.getMediaId('/')
        self.assertEqual(ret, None)      
        
    def mount_directory_1_test(self):   
        import pyanaconda.image
        pyanaconda.image.os.path.ismount = mock.Mock(return_value=False)
        pyanaconda.image.mountDirectory('hd:/dev/sda1:/', mock.Mock())
        self.assertEqual(pyanaconda.image.isys.method_calls,
            [('mount', ('/dev/sda1', '/mnt/isodir'), {'fstype': 'auto'})])
            
    def mount_directory_2_test(self):   
        import pyanaconda.image
        pyanaconda.image.os.path.ismount = mock.Mock(return_value=False)
        pyanaconda.image.mountDirectory('hd:sda1:/', mock.Mock())
        self.assertEqual(pyanaconda.image.isys.method_calls,
            [('mount', ('/dev/sda1', '/mnt/isodir'), {'fstype': 'auto'})])
            
    def mount_directory_3_test(self):   
        import pyanaconda.image
        pyanaconda.image.os.path.ismount = mock.Mock(return_value=True)
        pyanaconda.image.mountDirectory('hd:sda1:/', mock.Mock())
        self.assertEqual(pyanaconda.image.isys.method_calls, []) 
        
    def mount_image_1_test(self):
        import pyanaconda.image
        self.assertRaises(SystemError, pyanaconda.image.mountImage, '', '/mnt/cdimage', 1, mock.Mock())
     
    def mount_image_2_test(self):
        import pyanaconda.image
        pyanaconda.image.os.path.ismount = mock.Mock(return_value=False)
        ret = pyanaconda.image.mountImage('', '/mnt/cdimage', 1, mock.Mock(), 
            {1: IMAGENAME})

        self.assertEqual(ret,  {1: IMAGENAME})
        
        self.assertEqual(pyanaconda.image.isys.method_calls,
           [('mount', ('/Fedora-13-i386-DVD.iso', '/mnt/cdimage'), 
                                    {'readOnly': True, 'fstype': 'iso9660'})])
        
    def present_required_media_message_1_test(self):
        import pyanaconda.image
        anaconda = mock.Mock()
        anaconda.backend.getRequiredMedia.return_value = [1]
        ret = pyanaconda.image.presentRequiredMediaMessage(anaconda)
        self.assertEqual(ret, None)

    def present_required_media_message_2_test(self):
        import pyanaconda.image
        anaconda = mock.Mock()
        anaconda.backend.getRequiredMedia.return_value = [1, 2]
        anaconda.backend.ayum.tree = '/tmp'
        ret = pyanaconda.image.presentRequiredMediaMessage(anaconda)
        self.assertEqual(ret, None)
        
    def present_required_media_message_3_test(self):
        import pyanaconda.image
        anaconda = mock.Mock()
        anaconda.backend.getRequiredMedia.return_value = [1, 3]
        anaconda.backend.ayum.tree = '/tmp'
        pyanaconda.image.gettext.ldgettext.return_value = '%s'
        ret = pyanaconda.image.presentRequiredMediaMessage(anaconda)
        self.assertTrue(isinstance(ret, mock.Mock))
        
    def scan_for_media_1_test(self):
        import pyanaconda.image
        storage = mock.Mock()
        storage.devicetree.devices = []
        ret = pyanaconda.image.scanForMedia(mock.Mock(), storage)
        self.assertEqual(ret, None)
        
    def scan_for_media_2_test(self):
        import pyanaconda.image
        device = mock.Mock()
        device.type = 'cdrom'
        device.name = 'deviceName'
        storage = mock.Mock()
        storage.devicetree.devices = [device]
        ret = pyanaconda.image.scanForMedia('/tmp', storage)
        self.assertEqual(ret, 'deviceName')
        self.assertEqual(device.method_calls, 
            [('format.mount', (), {'mountpoint': '/tmp'})])
            
    def umount_image_1_test(self):
        import pyanaconda.image
        pyanaconda.image.umountImage('/tmp', None)
        self.assertEqual(pyanaconda.image.isys.method_calls, 
            [])
        
    def umount_image_2_test(self):
        import pyanaconda.image
        pyanaconda.image.umountImage('/tmp', mock.Mock())
        self.assertEqual(pyanaconda.image.isys.method_calls, 
            [('umount', ('/tmp',), {'removeDir': False})])
             
    def unmount_cd_1_test(self):
        import pyanaconda.image
        window = mock.Mock()
        pyanaconda.image.unmountCD(None, window)
        self.assertEqual(window.method_calls, [])

    def unmount_cd_2_test(self):
        import pyanaconda.image
        window = mock.Mock()
        device = mock.Mock()
        pyanaconda.image.unmountCD(device, window)
        self.assertEqual(window.method_calls, [])
        self.assertEqual(device.method_calls,
            [('format.unmount', (), {})])
        
    def verify_media_1_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.verifyMedia('/tmp', 1)
        self.assertTrue(ret)
        
    def verify_media_2_test(self):
        import pyanaconda.image
        ret = pyanaconda.image.verifyMedia('/tmp', 3)
        self.assertFalse(ret)
        
    def verify_media_3_test(self):
        import pyanaconda.image
        pyanaconda.image._arch = 'x86_64'
        ret = pyanaconda.image.verifyMedia('/tmp', 1)
        self.assertFalse(ret)
