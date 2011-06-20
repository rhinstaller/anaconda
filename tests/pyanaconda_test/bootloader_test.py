import mock

class BootloaderTest(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'pyanaconda.anaconda_log', 'block',
             'pyanaconda.storage',
             'pyanaconda.storage.devicelibs',
             'pyanaconda.storage.errors'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

    def tearDown(self):
        self.tearDownModules()

    def test_argument(self):
        from pyanaconda.bootloader import Arguments
        a = Arguments()
        a.update(set(["a", "b", "c"]))
        b = Arguments()
        b.add("b")
        diff = a - b
        self.assertEqual(diff, set(["a", "c"]))
        self.assertIsInstance(diff, Arguments)
        assert(str(diff) in ["a c", "c a"])
