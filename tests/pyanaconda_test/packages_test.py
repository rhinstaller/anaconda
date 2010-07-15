#!/usr/bin/python

import mock

class PackagesTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "block", "logging", "parted", "storage", 
                    "pyanaconda.storage.formats", "ConfigParser", 
                    "pyanaconda.storage.storage_log"])
        self.fs = mock.DiskIO()
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

        import pyanaconda.packages
        
    def tearDown(self):
        self.tearDownModules()
    
    def do_post_action_test(self):
        import pyanaconda.packages
        anaconda = mock.Mock()
        pyanaconda.packages.doPostAction(anaconda)
        self.assertTrue(anaconda.instClass.postAction.called)
