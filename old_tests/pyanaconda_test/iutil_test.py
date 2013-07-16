import mock
import sys

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
        self.assertEqual(iutil.copy_to_sysimage("/etc/securetty"), False)

        fs["/etc/securetty"] = "tty1"
        iutil.os.makedirs = mock.Mock()
        iutil.shutil.copy = mock.Mock()
        self.assertEqual(iutil.copy_to_sysimage("/etc/securetty"), True)
        iutil.os.makedirs.assert_called_with("/mnt/sysimage/etc")
        iutil.shutil.copy.assert_called_with("/etc/securetty",
                                             "/mnt/sysimage/etc/securetty")

    def testExecCaptureNonZeroFatal (self):
        import iutil
        try:
            argv = ["-c", "import sys; sys.exit(3);"]
            iutil.execWithCapture(sys.executable, argv, root=None, fatal=True)
        except RuntimeError, ex:
            self.assertIn("return code: 3", str(ex))
        else:
            self.fail("RuntimeError not raised")
