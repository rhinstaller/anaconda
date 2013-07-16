import mock

class DmSetupInfoLogMinerTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def action_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.DmSetupInfoLogMiner()
        obj._run_command = mock.Mock()
        obj._action()
        
        self.assertTrue(obj._run_command.called)

