#!/usr/bin/python

# Test Bug 500198

import mock
import sys


class FlagsTest(mock.TestCase):
    """Simulate /proc/cmdline parameters parsing (#500198)"""
    
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])
        
        self.fs = mock.DiskIO()
        
        import pyanaconda.flags
               
        self.mock2 = mock.Mock()
        pyanaconda.flags.open = mock.Mock(return_value=self.mock2)
    
    def tearDown(self):
        self.tearDownModules()
    
    def createcmdlinedict_1_test(self):
        """/proc/cmdline without BOOT_IMAGE param"""
        import pyanaconda.flags
        
        self.cmd = 'vmlinuz initrd=initrd.img stage2=hd:LABEL="Fedora" xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        cmddict = pyanaconda.flags.flags.createCmdlineDict()    

        self.assertEqual(set(cmddict.keys()), 
            set(['vmlinuz', 'initrd', 'stage2', 'xdriver', 'nomodeset']))

    def createcmdlinedict_2_test(self):
        """/proc/cmdline param: quotes at end"""
        import pyanaconda.flags
        
        self.cmd = 'vmlinuz BOOT_IMAGE=/boot/img initrd=initrd.img stage2=hd:LABEL="Fedora"'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        try:
            cmddict = pyanaconda.flags.flags.createCmdlineDict()
        except (ValueError):
            self.assertTrue(False, "ValueError exception was raised.")

        self.assertEqual(set(cmddict.keys()), 
            set(['vmlinuz', 'BOOT_IMAGE', 'initrd', 'stage2']))

    def createcmdlinedict_3_test(self):
        """/proc/cmdline param BOOT_IMAGE with quotes (no quotes at end)"""
        import pyanaconda.flags
                
        self.cmd = 'vmlinuz BOOT_IMAGE="img img" initrd=initrd.img'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        cmddict = pyanaconda.flags.flags.createCmdlineDict()    

        self.assertEqual(set(cmddict.keys()), 
            set(['vmlinuz', 'BOOT_IMAGE', 'initrd']))

    def createcmdlinedict_4_test(self):
        """/proc/cmdline param BOOT_IMAGE with quotes (no quotes at end) v2"""
        import pyanaconda.flags
                
        self.cmd = 'vmlinuz BOOT_IMAGE="/boot/img" stage2=hd:LABEL="Fedora" initrd=initrd.img'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        cmddict = pyanaconda.flags.flags.createCmdlineDict()    

        self.assertEqual(set(cmddict.keys()), 
            set(['vmlinuz', 'BOOT_IMAGE', 'initrd', 'stage2']))

    def createcmdlinedict_5_test(self):
        """/proc/cmdline param: BOOT_IMAGE with quotes (+ quotes at end)"""
        import pyanaconda.flags
                
        self.cmd = 'vmlinuz BOOT_IMAGE="/boot/img img" initrd=initrd.img stage2=hd:LABEL="Fedora"'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        try:
            cmddict = pyanaconda.flags.flags.createCmdlineDict()
        except (ValueError):
            self.assertTrue(False, "ValueError exception was raised.")

        self.assertEqual(set(cmddict.keys()), 
            set(['vmlinuz', 'BOOT_IMAGE', 'initrd', 'stage2']))
    
    def setattr_getattr_1_test(self):
        import pyanaconda.flags
        RET = 1
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        pyanaconda.flags.flags.sshd = RET
        self.assertEqual(RET, pyanaconda.flags.flags.sshd)
    
    def setattr_getattr_2_test(self):
        import pyanaconda.flags
        RET = 0
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        pyanaconda.flags.flags.sshd = RET
        self.assertEqual(RET, pyanaconda.flags.flags.sshd)
    
    def setattr_getattr_3_test(self):
        import pyanaconda.flags
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        
        def f(): return pyanaconda.flags.flags.fooattr
        self.assertRaises(AttributeError, f)
    
    def setattr_getattr_4_test(self):
        import pyanaconda.flags
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        
        def f(): pyanaconda.flags.flags.fooattr = 1
        self.assertRaises(AttributeError, f)
    
    def get_1_test(self):
        import pyanaconda.flags
        RET = 'text'
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        ret = pyanaconda.flags.flags.get('foobar', RET)
        self.assertEqual(RET, ret)
    
    def get_2_test(self):
        import pyanaconda.flags
        RET = 'text'
        self.cmd = 'vmlinuz initrd=initrd.img xdriver=vesa nomodeset'
        self.mock2.read = mock.Mock(return_value=self.cmd)
        ret = pyanaconda.flags.flags.get('sshd', RET)
        self.assertNotEqual(RET, ret)
