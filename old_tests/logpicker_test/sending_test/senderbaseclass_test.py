import mock

class SenderBaseClassTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def get_description_1_test(self):
        import log_picker.sending.senderbaseclass as senderbaseclass
        
        HOSTNAME = "tiger"
        DATE = "2010-10-10"
        
        senderbaseclass.gethostname = mock.Mock(return_value = HOSTNAME)
        
        senderbaseclass.datetime = mock.Mock()
        senderbaseclass.datetime.datetime.now().strftime.return_value = DATE
        
        obj = senderbaseclass.SenderBaseClass()
        ret = obj._get_description()
        self.assertEqual(ret, "%s (%s) %s" % ("", HOSTNAME, DATE))
    
    def get_description_2_test(self):
        import log_picker.sending.senderbaseclass as senderbaseclass
        
        PREFIX = "description"
        HOSTNAME = "lion"
        DATE = "2011-11-11"
        
        senderbaseclass.gethostname = mock.Mock(return_value = HOSTNAME)
        
        senderbaseclass.datetime = mock.Mock()
        senderbaseclass.datetime.datetime.now().strftime.return_value = DATE
        
        obj = senderbaseclass.SenderBaseClass()
        ret = obj._get_description(PREFIX)
        self.assertEqual(ret, "%s (%s) %s" % (PREFIX, HOSTNAME, DATE))

    def get_description_3_test(self):
        import log_picker.sending.senderbaseclass as senderbaseclass
        
        PREFIX = "description"
        DATE = "2012-12-12"
        
        senderbaseclass.gethostname = mock.Mock(side_effect=Exception)
        
        senderbaseclass.datetime = mock.Mock()
        senderbaseclass.datetime.datetime.now().strftime.return_value = DATE
        
        obj = senderbaseclass.SenderBaseClass()
        ret = obj._get_description(PREFIX)
        self.assertEqual(ret, "%s (%s) %s" % (PREFIX, "", DATE))

