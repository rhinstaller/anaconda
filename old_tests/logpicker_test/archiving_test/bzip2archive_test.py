import os
import mock
import tempfile
from log_picker.archiving import ArchivationError


class Bzip2ArchiveTest(mock.TestCase):
    def setUp(self):
        self.tmp_files = []
        pass
    
    def _get_tmp(self):
        _, filename = tempfile.mkstemp()
        self.tmp_files.append(filename)
        return filename
    
    def tearDown(self):
        for file in self.tmp_files:
            os.unlink(file)
    
    def mimetype_test(self):
        from log_picker.archiving import Bzip2Archive
        obj = Bzip2Archive(usetar=True)
        ret = obj.mimetype
        self.assertEqual(ret, 'application/x-bzip2')
    
    def support_compression_test(self):
        from log_picker.archiving import Bzip2Archive
        obj = Bzip2Archive(usetar=True)
        ret = obj.support_compression
        self.assertTrue(ret)
    
    def file_ext_1_test(self):
        from log_picker.archiving import Bzip2Archive
        obj = Bzip2Archive(usetar=True)
        ret = obj.file_ext
        self.assertEqual(ret, '.tar.bz2')
    
    def file_ext_2_test(self):
        from log_picker.archiving import Bzip2Archive
        obj = Bzip2Archive(usetar=False)
        ret = obj.file_ext
        self.assertEqual(ret, '.bz2')
    
    def create_archive_1_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        infile1 = self._get_tmp()
        infile2 = self._get_tmp()
        
        obj = Bzip2Archive(usetar=False)
        self.assertRaises(ArchivationError, obj.create_archive, out_filename, \
                            [infile1, infile2])
        
    def create_archive_2_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        
        obj = Bzip2Archive(usetar=False)
        self.assertRaises(ArchivationError, obj.create_archive, out_filename, [])

    def create_archive_3_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        
        obj = Bzip2Archive(usetar=True)
        self.assertRaises(ArchivationError, obj.create_archive, out_filename, [])
    
    def create_archive_4_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        infile1 = self._get_tmp()
        infile2 = self._get_tmp()
        
        obj = Bzip2Archive(usetar=True)
        # Because both files (infile1 and infile2) are empty
        self.assertRaises(ArchivationError, obj.create_archive, out_filename, 
                            [infile1, infile2])

    def create_archive_5_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        infile1 = self._get_tmp()
        infile2 = self._get_tmp()
        open(infile1, 'w').write('abcdefghijklmnopqrstuvwxyz')
        open(infile2, 'w').write('1234567890')
        
        obj = Bzip2Archive(usetar=True)
        obj.create_archive(out_filename, [infile1, infile2])
        self.assertTrue(os.path.getsize(out_filename))
    
    def create_archive_6_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        infile1 = self._get_tmp()
        open(infile1, 'w').write('abcdefghijklmnopqrstuvwxyz')
        
        obj = Bzip2Archive(usetar=False)
        obj.create_archive(out_filename, [infile1])
        self.assertTrue(os.path.getsize(out_filename))
    
    def create_archive_7_test(self):
        from log_picker.archiving import Bzip2Archive
        
        out_filename = self._get_tmp()
        infile1 = self._get_tmp()
        open(infile1, 'w').write('abcdefghijklmnopqrstuvwxyz')
        
        obj = Bzip2Archive(usetar=True)
        obj.create_archive(out_filename, [infile1])
        self.assertTrue(os.path.getsize(out_filename))
        
    
