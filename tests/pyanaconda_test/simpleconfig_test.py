#!/usr/bin/python

import mock
import os
import sys

class SimpleconfigTest(mock.TestCase):
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])
        import pyanaconda.simpleconfig

        # Stuff for IfcfgFile class tests
        self.DIR = '/tmp/'
        self.IFACE = 'eth0'
        self.PATH = "%sifcfg-%s" % (self.DIR, self.IFACE)
        self.CONTENT = '# Broadcom Corporation NetXtreme BCM5761 Gigabit Ethernet\n'
        self.CONTENT += 'DEVICE=eth0\n'
        self.CONTENT += 'HWADDR=00:10:18:61:35:98\n'
        self.CONTENT += 'ONBOOT=no\n'
        open(self.PATH, 'w').write(self.CONTENT)

    def tearDown(self):
        self.tearDownModules()

    def uppercase_ascii_string_letters_test(self):
        """Converting to uppercase (letters)"""
        import pyanaconda.simpleconfig
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('abcd')
        self.assertEqual(ret, 'ABCD')
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('aBCD')
        self.assertEqual(ret, 'ABCD')
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('ABCD')
        self.assertEqual(ret, 'ABCD')

    def uppercase_ascii_string_numbers_test(self):
        """Converting to uppercase (numbers)"""
        import pyanaconda.simpleconfig
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('123')
        self.assertEqual(ret, '123')

    def uppercase_ascii_string_others_test(self):
        """Converting to uppercase (special chars)"""
        import pyanaconda.simpleconfig
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('--')
        self.assertEqual(ret, '--')
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string(' ')
        self.assertEqual(ret, ' ')
        ret = pyanaconda.simpleconfig.uppercase_ASCII_string('')
        self.assertEqual(ret, '')

    def unquote_test(self):
        from pyanaconda.simpleconfig import unquote
        self.assertEqual(unquote("plain string"), "plain string")
        self.assertEqual(unquote('"double quote"'), "double quote")
        self.assertEqual(unquote("'single quote'"), "single quote")

    def quote_test(self):
        from pyanaconda.simpleconfig import quote
        self.assertEqual(quote("nospaces"), "nospaces")
        self.assertEqual(quote("plain string"), '"plain string"')
        self.assertEqual(quote("alwaysquote", always=True), '"alwaysquote"')

    def set_and_get_test(self):
        """Setting and getting values"""
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.SimpleConfigFile()
        scf.set(('key1', 'value1'))
        self.assertEqual(scf.get('key1'), 'value1')
        scf.set(('KEY2', 'value2'))
        self.assertEqual(scf.get('key2'), 'value2')
        scf.set(('KEY3', 'value3'))
        self.assertEqual(scf.get('KEY3'), 'value3')
        scf.set(('key4', 'value4'))
        self.assertEqual(scf.get('KEY4'), 'value4')

    def unset_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.SimpleConfigFile()
        scf.set(('key1', 'value1'))
        scf.unset(('key1'))
        self.assertEqual(scf.get('key1'), '')

    def write_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.SimpleConfigFile()
        scf.set(('key1', 'value1'))
        scf.write('/tmp/file')
        self.assertEqual(open('/tmp/file').read(), 'KEY1=value1\n')

    def read_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.SimpleConfigFile()
        open('/tmp/file', 'w').write('KEY1="value1"\n')
        scf.read('/tmp/file')
        self.assertEqual(scf.get('key1'), 'value1')

    def read_write_test(self):
        from pyanaconda.simpleconfig import SimpleConfigFile
        scf = SimpleConfigFile()
        scf.read(self.PATH)
        scf.write("/tmp/file")
        self.assertEqual(open("/tmp/file").read(), self.CONTENT)

    def write_new_keys_test(self):
        from pyanaconda.simpleconfig import SimpleConfigFile
        scf = SimpleConfigFile()
        scf.read(self.PATH)
        scf.set(("key1", "value1"))
        scf.write("/tmp/file")
        self.assertEqual(open("/tmp/file").read(),
                         self.CONTENT+"KEY1=value1\n")

    def remove_key_test(self):
        from pyanaconda.simpleconfig import SimpleConfigFile
        scf = SimpleConfigFile()
        scf.read(self.PATH)
        scf.unset("BOOT")
        scf.write("/tmp/file")
        scf.reset()
        scf.read("/tmp/file")
        self.assertEqual(scf.get("BOOT"), "")

    def ifcfgfile_path_property_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.IfcfgFile(self.DIR, self.IFACE)
        self.assertEqual(scf.path, self.PATH)

    def ifcfgfile_read_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.IfcfgFile(self.DIR, self.IFACE)
        scf.read()
        self.assertEqual(scf.get('device'), 'eth0')
        self.assertEqual(scf.get('hwaddr'), '00:10:18:61:35:98')
        self.assertEqual(scf.get('onboot'), 'no')

    def ifcfgfile_read_and_clear_test(self):
        import pyanaconda.simpleconfig        
        scf = pyanaconda.simpleconfig.IfcfgFile(self.DIR, self.IFACE)
        scf.read()
        scf.clear()
        self.assertEqual(scf.get('device'), '')
        self.assertEqual(scf.get('hwaddr'), '')
        self.assertEqual(scf.get('onboot'), '')

    def ifcfgfile_write_test(self):
        import pyanaconda.simpleconfig
        scf = pyanaconda.simpleconfig.IfcfgFile(self.DIR, self.IFACE)
        scf.set(('device', 'eth0'))
        scf.set(('hwaddr', '00:11:22:33:44:55'))
        scf.set(('onboot', 'no'))
        scf.write()
        self.assertEqual(open(self.PATH).read(),
            'DEVICE="eth0"\nHWADDR="00:11:22:33:44:55"\nONBOOT="no"\n')

