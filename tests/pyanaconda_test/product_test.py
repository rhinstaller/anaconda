#!/usr/bin/python

import mock
import sys
import __builtin__

import ConfigParser

class ProductTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(['_isys', 'block', 'os'])
        self.fs = mock.DiskIO()
        
        del sys.modules['pyanaconda.product']
              
        # os module global mock
        self.modifiedModule("os")
        os = sys.modules['os']
        os.access = mock.Mock(return_value=False)
        os.uname.return_value = ('', '', '', '', 'i386')
        os.environ = {}      
    
        # fake /tmp/product/.buildstamp file
        self.BUGURL = 'http://bug.url'
        self.BETA = 'true'
        self.ARCH = 'i386'
        self.NAME = '__anaconda'
        self.UUID = '123456.%s' % self.ARCH
        self.VERSION = '14'
        self.FILENAME = '/tmp/product/.buildstamp'
        self.FILE = \
        "[Main]\n"\
        "BugURL: %s\n"\
        "IsBeta: %s\n"\
        "Arch: %s\n"\
        "Product: %s\n"\
        "UUID: %s\n"\
        "Version: %s\n" % \
        (self.BUGURL, self.BETA, self.ARCH, self.NAME, self.UUID, self.VERSION)
        
        self.fs.open(self.FILENAME, 'w').write(self.FILE)
        
        # mock builtin open function
        self.open = __builtin__.open
        __builtin__.open = self.fs.open
        
    def tearDown(self):
        __builtin__.open = self.open
        self.tearDownModules()
    
   
    def bug_url_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertEqual(pyanaconda.product.bugUrl, self.BUGURL)
    
    def is_beta_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertTrue(pyanaconda.product.isBeta)
    
    def product_arch_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertEqual(pyanaconda.product.productArch, self.ARCH)
   
    def product_name_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertEqual(pyanaconda.product.productName, self.NAME)

    def product_stamp_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertEqual(pyanaconda.product.productStamp, self.UUID)
    
    def product_version_test(self):
        sys.modules['os'].access = mock.Mock(return_value=True)
        import pyanaconda.product
        self.assertEqual(pyanaconda.product.productVersion, self.VERSION)

