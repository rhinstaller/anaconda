#!/usr/bin/python

import mock

class LiloTest(mock.TestCase):
    only = True
    def setUp(self):
        self.setupModules(['_isys', 'block', 'parted', 'storage',
                            'pyanaconda.storage.formats', 'logging', 
                            'ConfigParser', 'pyanaconda.storage.storage_log'])
        
        self.fs = mock.DiskIO()
      
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()
        
        import pyanaconda.booty.lilo
        pyanaconda.booty.lilo.open = self.fs.open
        
        self.LFILE = '/tmp/lilo.conf'
        self.LILO_CFG = (
            "boot=/dev/hda\n"
            "map=/boot/map\n"
            "install=/boot/boot.b\n"
            "compact\n"
            "prompt\n"
            "timeout=50\n"
            "\n"
            "image=/boot/vmlinuz-2.0.36\n"
	        "\tlabel=linux\n"
	        "\talias=foo\n"
            "\troot=/dev/hda2\n"
            "\tread-only\n"
            "\n"
            "other=/dev/hda1\n"
            "\tlabel=win\n")
            
        self.LFILE_OTHER = '/tmp/lilo.conf_other'
        self.LILO_CFG_OTHER = (
            "boot=/dev/hda\n"
            "map=/boot/map\n"
            "install=/boot/boot.b\n"
            "compact\n"
            "prompt\n"
            "timeout=50\n"
            "\n"
            "other=/dev/hda1\n"
            "\tlabel=win\n")
            
        self.LFILE_DO = '/tmp/lilo.conf_do'
        self.LILO_CFG_DO = (
            "boot=/dev/hda\n"
            "map=/boot/map\n"
            "default=win\n"
            "install=/boot/boot.b\n"
            "compact\n"
            "prompt\n"
            "timeout=50\n"
            "\n"
            "image=/boot/vmlinuz-2.0.36\n"
	        "\tlabel=linux\n"
	        "\talias=foo\n"
            "\troot=/dev/hda2\n"
            "\tread-only\n"
            "\n"
            "other=/dev/hda1\n"
            "\tlabel=win\n")
  
        self.fs.open(self.LFILE, 'w').write(self.LILO_CFG)
        self.fs.open(self.LFILE_OTHER, 'w').write(self.LILO_CFG_OTHER)
        self.fs.open(self.LFILE_DO, 'w').write(self.LILO_CFG_DO)
     
    def tearDown(self):
        self.tearDownModules()

    def add_entry_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        conf.addEntry('fooentry', '55')
        ret = conf.getEntry('fooentry')
        self.assertEqual(ret, '55')

    def add_entry_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        conf.addEntry('fooentry', '55')
        conf.addEntry('fooentry', '22', replace=0)
        ret = conf.getEntry('fooentry')
        self.assertEqual(ret, '55')

    def get_entry_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getEntry('timeout')
        self.assertEqual(ret, '50')
        
    def get_entry_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getEntry('foofoofoo')
        self.assertEqual(ret, None)

    def del_entry_key_exists_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        conf.delEntry('timeout')
        ret = conf.getEntry('timeout')
        self.assertEqual(ret, None)

    def del_entry_key_does_not_exist_test(self):
        # This test fails
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        self.assertRaises(KeyError, conf.delEntry, 'foofoofoo')

    def list_entries_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.listEntries()
        self.assertEqual(ret, {'compact': None, 'map': '/boot/map', 
            'prompt': None, 'install': '/boot/boot.b', 'boot': '/dev/hda', 
            'timeout': '50'})

    def test_entry_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.testEntry('timeout')
        self.assertTrue(ret)

    def test_entry_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.testEntry('entryentryentry')
        self.assertFalse(ret)

    def get_image_by_label_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getImage('linux')
        self.assertEqual(repr(ret),
            "('image', label=linux\nalias=foo\nroot=/dev/hda2\nread-only\n, "
            "'/boot/vmlinuz-2.0.36', None)"
        )
        
    def get_image_by_alias_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getImage('foo')
        self.assertEqual(repr(ret),
            "('image', label=linux\nalias=foo\nroot=/dev/hda2\nread-only\n, "
            "'/boot/vmlinuz-2.0.36', None)"
        )

    def get_image_raise_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        self.assertRaises(IndexError, conf.getImage, ('foobar'))

    def add_image_1_test(self):
        import pyanaconda.booty.lilo
        img = mock.Mock()
        img.path='foopath'
        img.imageType='footype'
        img.getEntry.return_value = 'foo'
        img.imageType = 'image'
        img.path = '/boot/foo'
        img.other = None
        
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.addImage(img)
        
        ret = conf.getImage('foo')
        self.assertEqual(ret[0], 'image')
        # ret[1] is mock object instance
        self.assertEqual(ret[2], '/boot/foo')
        self.assertEqual(ret[3], None)
        
    def add_image_raise_test(self):
        import pyanaconda.booty.lilo
        image = pyanaconda.booty.lilo.LiloConfigFile()
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        self.assertRaises(ValueError, conf.addImage, (image))

    def del_image_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        conf.delImage('linux')
        conf.delImage('win')
        self.assertEqual(repr(conf), 
            'boot=/dev/hda\nmap=/boot/map\ninstall=/boot/boot.b\ncompact\nprompt\ntimeout=50\n') 

    def del_image_raise_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        self.assertRaises(IndexError, conf.delImage, ('barfoo'))        

    def get_default_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getDefault()
        self.assertEqual(repr(ret), "label=linux\nalias=foo\nroot=/dev/hda2\nread-only\n")

    def get_default_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE_OTHER)
        ret = conf.getDefault()
        self.assertEqual(repr(ret), "label=win\n")

    def get_default_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE_DO)
        ret = conf.getDefault()
        self.assertEqual(repr(ret), "label=win\n")

    def get_default_linux_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.getDefaultLinux()
        self.assertEqual(repr(ret), "label=linux\nalias=foo\nroot=/dev/hda2\nread-only\n")

    def get_default_linux_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE_OTHER)
        ret = conf.getDefaultLinux()
        self.assertEqual(ret, None)

    def get_default_linux_3_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE_DO)
        ret = conf.getDefaultLinux()
        self.assertEqual(repr(ret), "label=linux\nalias=foo\nroot=/dev/hda2\nread-only\n")

    def list_images_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.listImages()
        self.assertEqual(ret, ['linux', 'win'])

    def list_aliases_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        ret = conf.listAliases()
        self.assertEqual(ret, ['foo'])

    def get_path_test(self):
        import pyanaconda.booty.lilo
        PATH = '/tmp/path'
        conf = pyanaconda.booty.lilo.LiloConfigFile(path=PATH)
        ret = conf.path
        self.assertEqual(ret, PATH)

    def write_test(self):
        import pyanaconda.booty.lilo
        pyanaconda.booty.lilo.os = mock.Mock()
        pyanaconda.booty.lilo.os.chmod = mock.Mock()
        WFILE = '/tmp/lilo.conf_out'
        
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        conf.write(WFILE)
        self.assertEqual(self.fs[WFILE], self.LILO_CFG)

    def read_1_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE)
        self.assertEqual(repr(conf), self.LILO_CFG)

    def read_2_test(self):
        import pyanaconda.booty.lilo
        conf = pyanaconda.booty.lilo.LiloConfigFile()
        conf.read(self.LFILE_OTHER)
        self.assertEqual(repr(conf), self.LILO_CFG_OTHER)
        
