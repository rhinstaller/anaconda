import mock

class BugzillaBaseClassTest(mock.TestCase):
    def setUp(self):
        self.setupModules(['report.plugins.bugzilla', 
                            'report.plugins.bugzilla.filer'])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def connect_and_login_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        bugzillasender.filer = mock.Mock()
        
        USERNAME = "user"
        PASSWORD = "foopassword"
        
        obj = bugzillasender.BugzillaBaseClass()
        obj.connect_and_login(USERNAME, PASSWORD)
        
        self.assertTrue(bugzillasender.filer.BugzillaFiler().login.called)
        self.assertEqual(bugzillasender.filer.BugzillaFiler().login.call_args,
                            (('user', 'foopassword'), {}))
    
    def connect_and_login_fail_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        bugzillasender.filer = mock.Mock()
        bugzillasender.filer.BugzillaFiler().login.side_effect = \
                                        bugzillasender.LoginError('foo', 'bar')
        
        USERNAME = "user"
        PASSWORD = "foopassword"
        
        obj = bugzillasender.BugzillaBaseClass()
        self.assertRaises(bugzillasender.SenderError, obj.connect_and_login, \
                                                            USERNAME, PASSWORD)
        self.assertTrue(bugzillasender.filer.BugzillaFiler().login.called)
        self.assertEqual(bugzillasender.filer.BugzillaFiler().login.call_args,
                            (('user', 'foopassword'), {}))
    
    def set_bug_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        BUGID = "123456789"
        
        obj = bugzillasender.BugzillaBaseClass()
        obj.set_bug(BUGID)
        
        self.assertEqual(BUGID, obj.bug_id)
    
    def set_comment_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        COMMENT = "some comment"
        
        obj = bugzillasender.BugzillaBaseClass()
        obj.set_comment(COMMENT)
        
        self.assertEqual(COMMENT, obj.comment)
    
    def sendfile_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        bugzillasender.os = mock.Mock()
        bugzillasender.os.path = mock.Mock()
        bugzillasender.os.path.basename = lambda x: x
        
        FILE = "/tmp/somefile"
        MIMETYPE = "text/plain"
        
        obj = bugzillasender.BugzillaBaseClass()
        obj._get_description = mock.Mock()
        obj.bzfiler = mock.Mock()
        obj.sendfile(FILE, MIMETYPE)
        
        self.assertTrue(obj._get_description.called)
        self.assertTrue(obj.bzfiler.getbug.called)
        self.assertTrue(obj.bzfiler.getbug().attachfile.called)
    
    def sendfile_raise_test(self):
        import log_picker.sending.bugzillasender as bugzillasender
        
        bugzillasender.os = mock.Mock()
        bugzillasender.os.path = mock.Mock()
        bugzillasender.os.path.basename = lambda x: x
        
        FILE = "/tmp/somefile"
        MIMETYPE = "text/plain"
        
        obj = bugzillasender.BugzillaBaseClass()
        obj._get_description = mock.Mock()
        obj.bzfiler = mock.Mock()
        obj.bzfiler.getbug.side_effect = ValueError('Test exception')
        
        self.assertRaises(bugzillasender.SenderError, obj.sendfile, FILE, MIMETYPE)

