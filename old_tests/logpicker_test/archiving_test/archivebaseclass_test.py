import mock

class ArchiveBaseClassTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def create_tmp_tar_test(self):
        import log_picker.archiving as archiving
               
        FILE1 = "/tmp/abcd/file1"
        FILE2 = "/tmp/abcd/file2"
        FILELIST = [FILE1, FILE2]
        TMPFILE = "/tmp/tmpfile.tar"
        
        archiving.tempfile = mock.Mock()
        archiving.tempfile.mkstemp.return_value = "", TMPFILE
        archiving.tarfile = mock.Mock()
        
        self.fs.open(FILE1, 'w').write('1\n')
        self.fs.open(FILE2, 'w').write('2\n')
        self.fs.open(TMPFILE, 'w')
        
        obj = archiving.ArchiveBaseClass()
        ret = obj._create_tmp_tar(FILELIST)
        
        self.assertEqual(TMPFILE, ret)
        self.assertEqual(archiving.tarfile.open().add.call_args_list, 
            [((FILE1,), {'arcname': 'abcd/file1'}), 
             ((FILE2,), {'arcname': 'abcd/file2'})]
         )

