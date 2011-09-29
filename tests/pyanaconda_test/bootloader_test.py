import mock

class ArgumentsTest(mock.TestCase):
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

    def test_basic(self):
        from pyanaconda.bootloader import Arguments
        a = Arguments()
        a.update(set(["a", "b", "c"]))
        b = Arguments()
        b.add("b")
        diff = a - b
        self.assertEqual(diff, set(["a", "c"]))
        self.assertIsInstance(diff, Arguments)
        assert(str(diff) in ["a c", "c a"])

    def test_merge_ip(self):
        from pyanaconda.bootloader import Arguments
        # test that _merge_ip() doesnt break the simple case:
        a = Arguments(["one", "two", "ip=eth0:dhcp"])
        a._merge_ip()
        self.assertEqual(a, Arguments(["one", "two", "ip=eth0:dhcp"]))

        # test that it does what it's supposed to:
        a = Arguments(["one", "two", "ip=eth0:dhcp", "ip=eth0:auto6",
                       "ip=wlan0:dhcp",
                       "ip=10.34.102.102::10.34.39.255:24:aklab:eth2:none"])
        a._merge_ip()
        self.assertEqual(a, set([
                    "one", "two",
                    "ip=wlan0:dhcp",
                    "ip=10.34.102.102::10.34.39.255:24:aklab:eth2:none",
                    "ip=eth0:auto6,dhcp"]))

    def test_output_with_merge(self):
        from pyanaconda.bootloader import Arguments
        a = Arguments(["ip=eth0:dhcp"])
        self.assertEqual(str(a), "ip=eth0:dhcp")
        a = Arguments(["ip=eth0:dhcp", "ip=eth0:auto6"])
        assert(str(a) in ["ip=eth0:auto6,dhcp", "ip=eth0:dhcp,auto6"])

    def test_sorting(self):
        from pyanaconda.bootloader import Arguments
        a = Arguments(["ip=eth0:dhcp", "rhgb", "quiet",
                       "root=/dev/mapper/destroyers-rubies", "rd.md=0",
                       "rd.luks=0"])
        # 'rhgb quiet' should be the final entries:
        assert(str(a).endswith("rhgb quiet"))
