import mock

class StrataSenderTest(mock.TestCase):
    def setUp(self):
        self.setupModules(['report.plugins.strata'])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def set_login_test(self):
        import log_picker.sending.stratasender as stratasender
        
        LOGIN = "foo"
        PASSWORD = "bar"
        
        obj = stratasender.StrataSender()
        obj.set_login(LOGIN, PASSWORD)
        
        self.assertEqual(LOGIN, obj.username)
        self.assertEqual(PASSWORD, obj.password)
    
    def set_case_number_test(self):
        import log_picker.sending.stratasender as stratasender
        
        CASE_NUM = "123"
        
        obj = stratasender.StrataSender()
        obj.set_case_number(CASE_NUM)
        self.assertEqual(CASE_NUM, obj.case_number)
    
    def sendfile_test(self):
        import log_picker.sending.stratasender as stratasender
        
        FILE = "/tmp/somefile"
        RESPONSE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <response><title>File Attachment Succeeded</title><body>.</body></response>'''
        
        stratasender.send_report_to_existing_case = mock.Mock(return_value=RESPONSE)
        
        obj = stratasender.StrataSender()
        obj.sendfile(FILE, "")
        
        self.assertTrue(stratasender.send_report_to_existing_case.called)
    
    def sendfile_raise_1_test(self):
        import log_picker.sending.stratasender as stratasender
        
        FILE = "/tmp/somefile"
        RESPONSE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <response><title>File Attachment Failed</title><body>401 Unauthorized
        This request requires authentication....</body></response>'''
        
        stratasender.send_report_to_existing_case = mock.Mock(return_value=RESPONSE)
        
        obj = stratasender.StrataSender()
        self.assertRaises(stratasender.SenderError, obj.sendfile, FILE, "")
    
    def sendfile_raise_2_test(self):
        import log_picker.sending.stratasender as stratasender
        
        FILE = "/tmp/somefile"
        RESPONSE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <response><title>File Attachment Failed</title><body>Error : CASE_NOT_FOUND
        Message: Case 99999999 does not exist</body></response>'''
        
        stratasender.send_report_to_existing_case = mock.Mock(return_value=RESPONSE)
        
        obj = stratasender.StrataSender()
        self.assertRaises(stratasender.SenderError, obj.sendfile, FILE, "")

    def sendfile_raise_3_test(self):
        import log_picker.sending.stratasender as stratasender
        
        FILE = "/tmp/somefile"
        RESPONSE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <response><title>File Attachment Failed</title><body>Error : Your
        computer is under attack of alien intruders (from Mars).</body></response>'''
        
        stratasender.send_report_to_existing_case = mock.Mock(return_value=RESPONSE)
        
        obj = stratasender.StrataSender()
        self.assertRaises(stratasender.SenderError, obj.sendfile, FILE, "")

    def sendfile_raise_4_test(self):
        import log_picker.sending.stratasender as stratasender
        
        FILE = "/tmp/somefile"
        RESPONSE = '''This is not XML valid response => something is wrong.'''
        
        stratasender.send_report_to_existing_case = mock.Mock(return_value=RESPONSE)
        
        obj = stratasender.StrataSender()
        self.assertRaises(stratasender.SenderError, obj.sendfile, FILE, "")

