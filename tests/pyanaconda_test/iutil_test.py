import mock

class IutilTest(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'pyanaconda.anaconda_log', 'block'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

    def tearDown(self):
        self.tearDownModules()

    def copy_to_sysimage_test(self):
        from pyanaconda import iutil
        fs = mock.DiskIO()
        self.take_over_io(fs, iutil)
        self.assertEqual(iutil.copy_to_sysimage("/etc/securetty", "/sysimage"),
                         False)

        fs["/etc/securetty"] = "tty1"
        iutil.os.makedirs = mock.Mock()
        iutil.shutil.copy = mock.Mock()
        self.assertEqual(iutil.copy_to_sysimage("/etc/securetty",
                                                "/sysimage/subdir"),
                         True)
        iutil.os.makedirs.assert_called_with("/sysimage/subdir/etc")
        iutil.shutil.copy.assert_called_with("/etc/securetty",
                                             "/sysimage/subdir/etc/securetty")
