import os
import sys
import mock


class LogPickerTest(mock.TestCase):
    def setUp(self):
        pass

    def getlogs_1_test(self):
        from log_picker import LogPicker

        miner = mock.Mock()
        
        obj = LogPicker(miners=[miner], use_one_file=True)
        obj.getlogs()
        
        self.assertTrue(miner.set_logfile.called)
        self.assertTrue(miner.getlog.called)
    
    def getlogs_2_test(self):
        from log_picker import LogPicker
        from log_picker.logmining import LogMinerError
        
        miner = mock.Mock()
        miner.getlog.side_effect = LogMinerError('Just a test')
        
        obj = LogPicker(miners=[miner], use_one_file=True)
        # Temporary redirect stderr output
        sys.stderr, backup = mock.Mock(), sys.stderr
        obj.getlogs()
        sys.stderr = backup
        
        self.assertTrue(True)
        
    def send_1_test(self):
        from log_picker import LogPicker
        
        sender = mock.Mock()
        
        obj = LogPicker(sender_obj=sender)
        obj.files = ["file"]
        obj.send()
        
        self.assertTrue(sender.sendfile.called)
        self.assertEqual(sender.sendfile.call_args, 
                                        (('file', 'text/plain'), {}))

    def send_2_test(self):
        from log_picker import LogPicker
        
        sender = mock.Mock()
        archiver = mock.Mock()
        archiver.mimetype = "application/anything"
        
        obj = LogPicker(sender_obj=sender, archive_obj=archiver)
        obj.files = ["file"]
        obj.archive = "file2"
        obj.send()
        
        self.assertTrue(sender.sendfile.called)
        self.assertEqual(sender.sendfile.call_args, 
                                        (('file2', 'application/anything'), {}))

    def create_archive_1_test(self):
        from log_picker import LogPicker
        
        archiver = mock.Mock()
        archiver.file_ext = ".zip"
                
        obj = LogPicker(archive_obj=archiver)
        obj.create_archive()
        
        self.assertTrue(archiver.create_archive.called)
    
    def get_tmp_file_test(self):
        from log_picker import LogPicker
        
        obj = LogPicker()
        ret = obj._get_tmp_file("name")
        self.assertTrue(os.path.isfile(ret))
    
    def errprint_test(self):
        from log_picker import LogPicker
        
        obj = LogPicker()
        # Temporary redirect stderr output
        sys.stderr, backup = mock.Mock(), sys.stderr
        obj._errprint("message")
        res, sys.stderr = sys.stderr, backup
        self.assertTrue(res.write.called)
        self.assertEqual(res.write.call_args[0][0], 'message\n')
        
