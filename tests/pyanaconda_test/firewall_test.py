import mock

class FirewallTest(mock.TestCase):
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])

        self.fs = mock.DiskIO()

        import pyanaconda.firewall

        self.modifiedModule("pyanaconda.firewall")
        self.modifiedModule("os.path")

        pyanaconda.firewall.open = self.fs.open
        pyanaconda.firewall.log = mock.Mock()
        pyanaconda.firewall.iutil = mock.Mock()
        pyanaconda.firewall.os = mock.Mock()
        pyanaconda.firewall.os.path = mock.Mock()
        pyanaconda.firewall.os.path.exists = self.fs.os_path_exists

    def tearDown(self):
        self.tearDownModules()

    def default_write_test(self):
        import pyanaconda.firewall
        fw = pyanaconda.firewall.Firewall()
        fw.write()

        self.assertEqual(pyanaconda.firewall.iutil.method_calls, [
            ("execWithRedirect",
             (
                 "/usr/sbin/lokkit",
                 [ "--quiet", "--nostart", "-f", "--service=ssh" ]
                 ),
             {
                 "root": "/mnt/sysimage",
                 "stdout": "/dev/null",
                 "stderr": "/dev/null",
                 }
             )
            ])
