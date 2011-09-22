import mock

class KernelArgumentsTestCase(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'anaconda_log', 'block', 'platform'])

    def tearDown(self):
        self.tearDownModules()

    def test_merge_ip(self):
        import booty
        ka = booty.KernelArguments(mock.Mock())

        # test that _merge_ip() doesnt break the simple case:
        args = set(["one", "two", "ip=eth0:dhcp"])
        self.assertEqual(ka._merge_ip(args),
                         set(["one", "two", "ip=eth0:dhcp"]))

        # test that it does what it's supposed to:
        args = set(["one", "two", "ip=eth0:dhcp", "ip=eth0:auto6",
                    "ip=wlan0:dhcp",
                    "ip=10.34.102.102::10.34.39.255:24:aklab:eth2:none"])
        self.assertEqual(ka._merge_ip(args), set([
                    "one", "two",
                    "ip=wlan0:dhcp",
                    "ip=10.34.102.102::10.34.39.255:24:aklab:eth2:none",
                    "ip=eth0:auto6,dhcp"]))
