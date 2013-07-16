import os
import shutil
import mock

class ScpSenderTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def set_path_test(self):
        import log_picker.sending.localsender as local_s
        
        PATH = "/tmp/somewhere"
        
        obj = local_s.LocalSender()
        obj.set_path(PATH)
        
        self.assertEqual(PATH, obj.path)
    
    def sendfile(self):
        import log_picker.sending.localsender as local_s
        
        PATH = "/tmp/a_logfile_xa54hfd4j/"
        FILE = "testfile"
        
        if os.path.exists(PATH):
            if os.path.isdir(PATH):
                shutil.rmtree(PATH)
            else:
                self.assertTrue(False, "Cannot create test directory: %s" % PATH)
        
        os.mkdir(PATH)
        
        obj = local_s.LocalSender()
        obj.set_path(PATH)
        obj.sendfile(FILE, "")
        
        files = len(os.listdir(PATH))
        
        shutil.rmtree(PATH)
        
        self.assertTrue(files)

