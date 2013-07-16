import mock

class FileSystemLogMinerTest(mock.TestCase):
    def setUp(self):
        self.setupModules([])
        self.fs = mock.DiskIO()
    
    def tearDown(self):
        self.tearDownModules()
    
    def size_conversion_1_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(24)
        self.assertEqual(size, 24)
        self.assertEqual(unit, "")
    
    def size_conversion_2_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(2400)
        self.assertEqual(size, 2.3)
        self.assertEqual(unit, "K")
    
    def size_conversion_3_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(1024)
        self.assertEqual(size, 1)
        self.assertEqual(unit, "K")
    
    def size_conversion_4_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(1048576)
        self.assertEqual(size, 1)
        self.assertEqual(unit, "M")
    
    def size_conversion_5_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(1160576)
        self.assertEqual(size, 1.1)
        self.assertEqual(unit, "M")
    
    def size_conversion_6_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(1073741824)
        self.assertEqual(size, 1)
        self.assertEqual(unit, "G")
    
    def size_conversion_7_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(1273741824)
        self.assertEqual(size, 1.2)
        self.assertEqual(unit, "G")
    
    def size_conversion_8_test(self):
        import log_picker.logmining as logmining
        
        obj = logmining.FileSystemLogMiner()
        size, unit = obj._size_conversion(0)
        self.assertEqual(size, 0)
        self.assertEqual(unit, "")

