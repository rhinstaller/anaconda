import mock

class FtpSenderTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def set_host_1_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        HOST = "foobar"
        
        obj = ftp_s.FtpSender()
        obj.set_host(HOST)
        
        self.assertEqual("ftp://%s" % HOST, obj.host)
    
    def set_host_2_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        HOST = "ftp://foobar"
        
        obj = ftp_s.FtpSender()
        obj.set_host(HOST)
        
        self.assertEqual(HOST, obj.host)
    
    def set_login_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        LOGIN = "spiderman"
        PASSWORD = "jarfly"
        
        obj = ftp_s.FtpSender()
        obj.set_login(LOGIN, PASSWORD)
        
        self.assertEqual(LOGIN, obj.username)
        self.assertEqual(PASSWORD, obj.password)

    def sendfile_1_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        ftp_s.open = self.fs.open
        ftp_s.ftplib = mock.Mock()
        ftp_s.os = mock.Mock()
        ftp_s.os.path.basename = lambda x: x
        ftp_s.file = lambda x: x
        
        HOST = "localhost"
        FILE = "/tmp/somefile"
        MIMETYPE = "application/x-bzip2"
        
        self.fs.open(FILE, 'w').write("some content")
        
        obj = ftp_s.FtpSender()
        obj.set_host(HOST)
        obj.sendfile(FILE, MIMETYPE)
        
        method_calls = ftp_s.ftplib.FTP().method_calls
        method_names = [x[0] for x in ftp_s.ftplib.FTP().method_calls] 
        
        # Check calls order
        self.assertEqual(method_names, 
                ['connect', 'login', 'cwd', 'set_pasv', 'storbinary', 'quit'])
        
        # Check arguments
        PARAMS = 1
        
        CONNECT = 0
        LOGIN = 1
        CWD = 2
        SET_PASV = 3
        STORBINARY = 4
        QUIT = 5
        
        self.assertEqual(method_calls[CONNECT][PARAMS], (HOST, 21))
        self.assertEqual(method_calls[LOGIN][PARAMS], ())
        self.assertEqual(method_calls[CWD][PARAMS], ('',))
        self.assertEqual(method_calls[SET_PASV][PARAMS], (True,))
        self.assertEqual(method_calls[STORBINARY][PARAMS], 
                                                    ('STOR %s' % FILE, FILE))
                                                            
    def sendfile_2_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        ftp_s.open = self.fs.open
        ftp_s.ftplib = mock.Mock()
        ftp_s.os = mock.Mock()
        ftp_s.os.path.basename = lambda x: x
        ftp_s.file = lambda x: x
        
        PORT = "55"
        HOST = "localhost"
        ADDRESS = "%s:%s" % (HOST, PORT)
        USERNAME = "foo"
        PASSWORD = "bar"
        FILE = "/tmp/somefile"
        MIMETYPE = "application/x-bzip2"
        
        self.fs.open(FILE, 'w').write("some content")
        
        obj = ftp_s.FtpSender()
        obj.set_host(ADDRESS)
        obj.set_login(USERNAME, PASSWORD)
        obj.sendfile(FILE, MIMETYPE)
        
        method_calls = ftp_s.ftplib.FTP().method_calls
        method_names = [x[0] for x in ftp_s.ftplib.FTP().method_calls] 
        
        # Check calls order
        self.assertEqual(method_names, 
                ['connect', 'login', 'cwd', 'set_pasv', 'storbinary', 'quit'])
        
        # Check arguments
        PARAMS = 1
        
        CONNECT = 0
        LOGIN = 1
        CWD = 2
        SET_PASV = 3
        STORBINARY = 4
        QUIT = 5
        
        self.assertEqual(method_calls[CONNECT][PARAMS], (HOST, PORT))
        self.assertEqual(method_calls[LOGIN][PARAMS], (USERNAME, PASSWORD))
        self.assertEqual(method_calls[CWD][PARAMS], ('',))
        self.assertEqual(method_calls[SET_PASV][PARAMS], (True,))
        self.assertEqual(method_calls[STORBINARY][PARAMS], 
                                                    ('STOR %s' % FILE, FILE))
    
    def sendfile_fail_test(self):
        import log_picker.sending.ftpsender as ftp_s
        
        ftp_s.open = self.fs.open
        ftp_s.ftplib = mock.Mock()
        ftp_s.os = mock.Mock()
        ftp_s.file = mock.Mock()
        import ftplib
        ftp_s.ftplib = mock.Mock()
        ftp_s.ftplib.all_errors = ftplib.all_errors
        ftp_s.ftplib.FTP().storbinary.side_effect = ftplib.error_temp("some")
        
        HOST = "localhost"
        FILE = "/tmp/somefile"
        MIMETYPE = "application/x-bzip2"
        
        self.fs.open(FILE, 'w').write("some content")
        
        obj = ftp_s.FtpSender()
        obj.set_host(HOST)
        self.assertRaises(ftp_s.SenderError, obj.sendfile, FILE, MIMETYPE)
        
        
