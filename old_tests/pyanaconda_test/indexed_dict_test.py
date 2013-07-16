import mock

class IndexedDictTest(mock.TestCase):
    def setUp(self):
        self.setupModules(['_isys'])

    def tearDown(self):
        self.tearDownModules()

    def instantiation_test(self):
        from pyanaconda.indexed_dict import IndexedDict
        d = IndexedDict()
        self.assertIsInstance(d, IndexedDict)

    def append_test(self):
        from pyanaconda.indexed_dict import IndexedDict
        d = IndexedDict()
        stored_data = [1, 2, 3]
        d["some_step"] = stored_data
        self.assertIs(d["some_step"], stored_data)

    def cant_append_test(self):
        from pyanaconda.indexed_dict import IndexedDict
        def assign_int(indexed_dict):
            indexed_dict[3] = [1, 2, 3]
        d = IndexedDict()
        self.assertRaises(TypeError, d.__setitem__, 3, [1, 2, 3])

    def referencing_test(self):
        from pyanaconda.indexed_dict import IndexedDict
        d = IndexedDict()
        d["first"] = 10
        d["second"] = 20
        d["third"] = 30
        self.assertEqual(d[0], 10)
        self.assertEqual(d[1], 20)
        self.assertEqual(d[2], 30)
        self.assertRaises(IndexError, d.__getitem__, 3)

    def index_test(self):
        from pyanaconda.indexed_dict import IndexedDict
        d = IndexedDict()
        d["first"] = 10
        d["second"] = 20
        d["third"] = 30

        self.assertEqual(d.index("first"), 0)
        self.assertEqual(d.index("second"), 1)
        self.assertEqual(d.index("third"), 2)
