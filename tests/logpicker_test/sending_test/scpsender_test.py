import mock

class ScpSenderTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def set_host_1_test(self):
        import log_picker.sending.scpsender as scp_s
        
        HOST = "localhost"
        
        obj = scp_s.ScpSender()
        obj.set_host(HOST)
        
        self.assertEqual(HOST, obj.host)
    
    def set_host_2_test(self):
        import log_picker.sending.scpsender as scp_s
        
        HOST = "localhost"
        PORT = 12345
        ADDRESS = "%s:%s" % (HOST, PORT)
        
        obj = scp_s.ScpSender()
        obj.set_host(ADDRESS)
        
        self.assertEqual(HOST, obj.host)
        self.assertEqual(PORT, obj.port)
    
    def set_host_3_test(self):
        import log_picker.sending.scpsender as scp_s
        
        HOST = "localhost"
        PORT = "abc"
        ADDRESS = "%s:%s" % (HOST, PORT)
        
        obj = scp_s.ScpSender()
        obj.set_host(ADDRESS)
        
        self.assertEqual(HOST, obj.host)
        self.assertEqual(None, obj.port)
    
    def set_login_test(self):
        import log_picker.sending.scpsender as scp_s
        
        USERNAME = "foo"
        
        obj = scp_s.ScpSender()
        obj.set_login(USERNAME)
        
        self.assertEqual(USERNAME, obj.username)
    
    def set_path_1_test(self):
        import log_picker.sending.scpsender as scp_s
        
        PATH = "/tmp/something"
        
        obj = scp_s.ScpSender()
        obj.set_path(PATH)
        
        self.assertEqual(PATH, obj.path)

    def set_path_2_test(self):
        import log_picker.sending.scpsender as scp_s
        
        obj = scp_s.ScpSender()
        obj.set_path(None)
        
        self.assertEqual(".", obj.path)
    
    def sendfile_test(self):
        import log_picker.sending.scpsender as scp_s
        
        FILE = "/tmp/file"
        MIMETYPE = "text/plain"
        USERNAME = "foo"
        HOST = "localhost"
        PATH = "/home/foo"
        
        scp_s.subprocess = mock.Mock()
        scp_s.subprocess.Popen().returncode = False
                
        obj = scp_s.ScpSender()
        obj.set_host(HOST)
        obj.set_login(USERNAME)
        obj.set_path(PATH)
        obj.sendfile(FILE, MIMETYPE)
        
        TARGET = "%s@%s:%s" % (USERNAME, HOST, PATH)
        self.assertTrue(TARGET in scp_s.subprocess.Popen.call_args[0][0])
    
    def sendfile_fail_1_test(self):
        import log_picker.sending.scpsender as scp_s
        
        FILE = "/tmp/file"
        MIMETYPE = "text/plain"
        
        scp_s.subprocess = mock.Mock()
        
        obj = scp_s.ScpSender()
        self.assertRaises(scp_s.SenderError, obj.sendfile, FILE, MIMETYPE)

