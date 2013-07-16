import mock

class EmailSenderTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()

    def set_comment_test(self):
        import log_picker.sending.emailsender as email_s
        
        COMMENT = "test comment"
        
        obj = email_s.EmailSender("", "", "", "")
        obj.set_comment(COMMENT)
        
        self.assertEqual(COMMENT, obj.comment)
    
    def sendfile_test(self):
        import log_picker.sending.emailsender as email_s
        
        FILE = "/tmp/some_file"
        MIMETYPE = "text/plain"
        
        email_s.smtplib = mock.Mock()
        email_s.open = self.fs.open
        self.fs.open(FILE, 'w').write('some file content\n')
               
        class Fake_MIMEMultipart(mock.Mock):
            def __getitem__(self, key):
                return self.__dict__[key]
            
            def __setitem__(self, key, value):
                self.__dict__[key] = value
        
        email_s.email = mock.Mock()
        email_s.email.mime.multipart.MIMEMultipart.return_value = \
                                                            Fake_MIMEMultipart()
               
        obj = email_s.EmailSender("", "", "", "")
        obj.sendfile(FILE, MIMETYPE)
        
        self.assertTrue(email_s.smtplib.SMTP().sendmail.called)
        self.assertTrue(email_s.smtplib.SMTP().quit.called)
        self.assertEqual(2,
            len(email_s.email.mime.base.MIMEBase().set_payload.call_args_list))
    
    def sendfile_fail_1_test(self):
        import log_picker.sending.emailsender as email_s
        
        FILE = "/tmp/some_file"
        MIMETYPE = "text/plain"
        
        email_s.smtplib = mock.Mock()
        import socket
        email_s.smtplib.socket.gaierror = socket.gaierror
        email_s.smtplib.SMTP.side_effect = email_s.smtplib.socket.gaierror()
        email_s.open = self.fs.open
        self.fs.open(FILE, 'w').write('some file content\n')
               
        class Fake_MIMEMultipart(mock.Mock):
            def __getitem__(self, key):
                return self.__dict__[key]
            
            def __setitem__(self, key, value):
                self.__dict__[key] = value
        
        email_s.email = mock.Mock()
        email_s.email.mime.multipart.MIMEMultipart.return_value = \
                                                        Fake_MIMEMultipart()
               
        obj = email_s.EmailSender("", "", "", "")
        self.assertRaises(email_s.SenderError, obj.sendfile, FILE, MIMETYPE)

    def sendfile_fail_2_test(self):
        import log_picker.sending.emailsender as email_s
        
        FILE = "/tmp/some_file"
        MIMETYPE = "text/plain"
        
        email_s.smtplib = mock.Mock()
        import smtplib
        email_s.smtplib.SMTPRecipientsRefused = smtplib.SMTPRecipientsRefused
        email_s.smtplib.SMTP().sendmail.side_effect = \
                                            smtplib.SMTPRecipientsRefused("")
        email_s.open = self.fs.open
        self.fs.open(FILE, 'w').write('some file content\n')
               
        class Fake_MIMEMultipart(mock.Mock):
            def __getitem__(self, key):
                return self.__dict__[key]
            
            def __setitem__(self, key, value):
                self.__dict__[key] = value
        
        email_s.email = mock.Mock()
        email_s.email.mime.multipart.MIMEMultipart.return_value = \
                                                        Fake_MIMEMultipart()
               
        obj = email_s.EmailSender("", "", "", "")
        self.assertRaises(email_s.SenderError, obj.sendfile, FILE, MIMETYPE)
    
