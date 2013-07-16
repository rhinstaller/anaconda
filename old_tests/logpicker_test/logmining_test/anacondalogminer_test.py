import mock

class AnacondaLogMinerTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def action_test(self):
        import log_picker.logmining as logmining
        
        ANACONDA_LOG = "anaconda-tb-log"
        ANACONDA_LOG_PATH = "/tmp/%s" % ANACONDA_LOG
        LOG_CONTENT = "Test content\n"
        
        self.fs.open(ANACONDA_LOG_PATH, 'w').write(LOG_CONTENT)
        
        logmining.os = mock.Mock()
        listdir_values = [[ANACONDA_LOG], []]
        logmining.os.listdir.side_effect = lambda x: listdir_values.pop()
        
        logmining.open = self.fs.open
        self.fs.open('/var/run/anaconda.pid', 'w').write('555\n')
        
        proc_mock = mock.Mock()
        proc_mock.returncode = 0
        logmining.subprocess = mock.Mock()
        logmining.subprocess.Popen.return_value = proc_mock
        
        logmining.time = mock.Mock()
        
        OUTFILE = '/tmp/outfile'
        f = self.fs.open(OUTFILE, 'w')
        
        obj = logmining.AnacondaLogMiner(f)
        obj._action()
        f.close()
        
        self.assertEqual(self.fs[OUTFILE],
                            "%s:\n%s\n" % (ANACONDA_LOG_PATH, LOG_CONTENT))
    
    def action_raise_1_test(self):
        import log_picker.logmining as logmining
        
        logmining.os = mock.Mock()
        listdir_values = [[]]
        logmining.os.listdir.side_effect = lambda x: listdir_values.pop()
        
        logmining.open = self.fs.open
        
        obj = logmining.AnacondaLogMiner()
        self.assertRaises(logmining.LogMinerError, obj._action)
    
    def action_raise_2_test(self):
        import log_picker.logmining as logmining
              
        logmining.os = mock.Mock()
        listdir_values = [[]]
        logmining.os.listdir.side_effect = lambda x: listdir_values.pop()
        
        logmining.open = self.fs.open
        self.fs.open('/var/run/anaconda.pid', 'w').write('555\n')
        
        proc_mock = mock.Mock()
        proc_mock.returncode = 1
        logmining.subprocess = mock.Mock()
        logmining.subprocess.Popen.return_value = proc_mock
                
        obj = logmining.AnacondaLogMiner()
        self.assertRaises(logmining.LogMinerError, obj._action)
    
    def action_raise_3_test(self):
        import log_picker.logmining as logmining
        
        ANACONDA_LOG = "anaconda-tb-log"
        ANACONDA_LOG_PATH = "/tmp/%s" % ANACONDA_LOG
        LOG_CONTENT = "Test content\n"
        
        self.fs.open(ANACONDA_LOG_PATH, 'w').write(LOG_CONTENT)
        
        logmining.os = mock.Mock()
        listdir_values = [[], []]
        logmining.os.listdir.side_effect = lambda x: listdir_values.pop()
        
        logmining.open = self.fs.open
        self.fs.open('/var/run/anaconda.pid', 'w').write('555\n')
        
        proc_mock = mock.Mock()
        proc_mock.returncode = 0
        logmining.subprocess = mock.Mock()
        logmining.subprocess.Popen.return_value = proc_mock
        
        logmining.time = mock.Mock()
        
        obj = logmining.AnacondaLogMiner()
        self.assertRaises(logmining.LogMinerError, obj._action)

    def action_raise_4_test(self):
        import log_picker.logmining as logmining
        
        ANACONDA_LOG = "different-log"
        ANACONDA_LOG_PATH = "/tmp/%s" % ANACONDA_LOG
        LOG_CONTENT = "Test content\n"
        
        self.fs.open(ANACONDA_LOG_PATH, 'w').write(LOG_CONTENT)
        
        logmining.os = mock.Mock()
        listdir_values = [[ANACONDA_LOG], []]
        logmining.os.listdir.side_effect = lambda x: listdir_values.pop()
        
        logmining.open = self.fs.open
        self.fs.open('/var/run/anaconda.pid', 'w').write('555\n')
        
        proc_mock = mock.Mock()
        proc_mock.returncode = 0
        logmining.subprocess = mock.Mock()
        logmining.subprocess.Popen.return_value = proc_mock
        
        logmining.time = mock.Mock()
               
        obj = logmining.AnacondaLogMiner()
        self.assertRaises(logmining.LogMinerError, obj._action)
        
