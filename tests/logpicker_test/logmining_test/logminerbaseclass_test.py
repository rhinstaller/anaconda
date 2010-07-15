import mock

class LogminingBaseClassTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def get_filename_test(self):
        from log_picker.logmining import LogMinerBaseClass
        
        ret = LogMinerBaseClass.get_filename()
        self.assertEqual(ret, LogMinerBaseClass._filename)
    
    def get_description_test(self):
        from log_picker.logmining import LogMinerBaseClass
        
        ret = LogMinerBaseClass.get_description()
        self.assertEqual(ret, LogMinerBaseClass._description)
    
    def set_logfile_test(self):
        from log_picker.logmining import LogMinerBaseClass
        
        FILENAME = "file123"
        
        obj = LogMinerBaseClass()
        obj.set_logfile(FILENAME)
        self.assertEqual(FILENAME, obj.logfile)
       
    def write_separator_test(self):
        import log_picker.logmining as logmining
        logmining.open = self.fs.open
        
        OUTFILE = '/tmp/logfile'
        f = self.fs.open(OUTFILE, 'w')
        
        obj = logmining.LogMinerBaseClass(f)
        obj._write_separator()
        f.close()
        
        self.assertEqual(self.fs[OUTFILE], '\n\n')
    
    def write_files_1_test(self):
        import log_picker.logmining as logmining
        logmining.open = self.fs.open
        
        FILE = '/tmp/infile'
        CONTENT = "some_random_456_content\n"
        self.fs.open(FILE, 'w').write(CONTENT)
        
        OUTFILE = '/tmp/logfile'
        f = self.fs.open(OUTFILE, 'w')
        
        obj = logmining.LogMinerBaseClass(f)
        obj._write_files(FILE)
        f.close()
               
        self.assertEqual('%s:\n%s\n' % (FILE, CONTENT), self.fs[OUTFILE])
        
    def write_files_2_test(self):
        import log_picker.logmining as logmining
        logmining.open = self.fs.open
        
        FILE_1 = '/tmp/infile1'
        FILE_2 = '/tmp/infile2'
        CONTENT_1 = "some_random_456_content\n"
        CONTENT_2 = "next_line_789\n"
        self.fs.open(FILE_1, 'w').write(CONTENT_1)
        self.fs.open(FILE_2, 'w').write(CONTENT_2)
        
        OUTFILE = '/tmp/logfile'
        f = self.fs.open(OUTFILE, 'w')
        
        obj = logmining.LogMinerBaseClass(f)
        obj._write_files([FILE_1, FILE_2])
        f.close()
               
        self.assertEqual('%s:\n%s\n%s:\n%s\n' % \
                (FILE_1, CONTENT_1, FILE_2, CONTENT_2), self.fs[OUTFILE])
    
    def run_command_test(self):
        import log_picker.logmining as logmining
               
        COMMAND = "some_command param1 param2"
        STDOUT = "some output"
        STDERR = "some error"
        RETCODE = 1
        
        proc_mock = mock.Mock()
        proc_mock.returncode = RETCODE
        proc_mock.communicate.return_value = (STDOUT, STDERR)
        logmining.subprocess = mock.Mock()
        logmining.subprocess.Popen.return_value = proc_mock
        
        OUTFILE = "/tmp/outfile"
        f = self.fs.open(OUTFILE, 'w')
        
        obj = logmining.LogMinerBaseClass(f)
        obj._run_command(COMMAND)
        f.close()
        
        self.assertEqual(self.fs[OUTFILE],
                "STDOUT:\nsome output\nSTDERR:\nsome error\nRETURN CODE: 1\n")

