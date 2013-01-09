#!/usr/bin/python

import mock
import os

class NetworkTest(mock.TestCase):

    def setUp(self):
        self.setupModules(['_isys', 'block', 'logging', 'ConfigParser'])
        self.fs = mock.DiskIO()

        self.OK = 22
        self.SYSCONFIGDIR = "/tmp/etc/sysconfig"
        self.NETSCRIPTSDIR = "%s/network-scripts" % (self.SYSCONFIGDIR)
        self.NETWORKCONFFILE = '%s/network' % self.SYSCONFIGDIR
        self.IFCFGLOG = '/tmp/ifcfg.log'
        self.DEFAULT_HOSTNAME = 'localhost.localdomain'

        self.CONT = "DEVICE=eth0\nHWADDR=00:11:22:50:55:50\nTYPE=Ethernet\nBOOTPROTO=dhcp\n"
        self.DEVICE = 'eth0'
        self.DEV_FILE =  self.NETSCRIPTSDIR + '/ifcfg-eth0'
        self.DEV_KEY_FILE =  self.NETSCRIPTSDIR + '/keys-eth0'
        self.fs.open(self.DEV_FILE, 'w').write(self.CONT)

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

        import pyanaconda.network
        pyanaconda.network.socket = mock.Mock()
        pyanaconda.network.socket.gethostname.return_value = self.DEFAULT_HOSTNAME
        pyanaconda.network.open = self.fs.open
        pyanaconda.simpleconfig.open = self.fs.open
        pyanaconda.network.sysconfigDir = self.SYSCONFIGDIR
        pyanaconda.network.netscriptsDir = self.NETSCRIPTSDIR
        pyanaconda.network.networkConfFile = self.NETWORKCONFFILE
        pyanaconda.network.ifcfgLogFile = self.IFCFGLOG
        self.fs.open(self.IFCFGLOG, 'w')

        # Network mock
        pyanaconda.network.Network.update = mock.Mock()
        self.setNMControlledDevices_backup = pyanaconda.network.Network.setNMControlledDevices
        pyanaconda.network.Network.setNMControlledDevices = mock.Mock()
        pyanaconda.network.Network.netdevices = {}

    def tearDown(self):
        self.tearDownModules()

    def sanity_check_hostname_1_test(self):
        import pyanaconda.network
        (valid, err) = pyanaconda.network.sanityCheckHostname('desktop')
        self.assertTrue(valid)

    def sanity_check_hostname_2_test(self):
        import pyanaconda.network
        (valid, err) = pyanaconda.network.sanityCheckHostname('')
        self.assertFalse(valid)

    def sanity_check_hostname_3_test(self):
        import pyanaconda.network
        (valid, err) = pyanaconda.network.sanityCheckHostname('c'*256)
        self.assertFalse(valid)

    def sanity_check_hostname_4_test(self):
        import pyanaconda.network
        (valid, err) = pyanaconda.network.sanityCheckHostname('_asf')
        self.assertFalse(valid)

    def sanity_check_hostname_5_test(self):
        import pyanaconda.network
        (valid, err) = pyanaconda.network.sanityCheckHostname('a?f')
        self.assertFalse(valid)

    def get_default_hostname_1_test(self):
        import pyanaconda.network

        HOSTNAME = 'host1'
        pyanaconda.network.getActiveNetDevs = mock.Mock(return_value=['dev'])
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.getIPAddresses.return_value = ['10.0.0.1']
        pyanaconda.network.socket = mock.Mock()
        pyanaconda.network.socket.gethostbyaddr.return_value = [HOSTNAME, '', '']

        ret = pyanaconda.network.getDefaultHostname(mock.Mock())
        self.assertEqual(ret, HOSTNAME)

    def get_default_hostname_2_test(self):
        import pyanaconda.network

        HOSTNAME = 'host2'
        pyanaconda.network.getActiveNetDevs = mock.Mock(return_value=[])
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.socket = mock.Mock()
        anaconda = mock.Mock()
        anaconda.network.hostname = HOSTNAME

        ret = pyanaconda.network.getDefaultHostname(anaconda)
        self.assertEqual(ret, HOSTNAME)

    def get_default_hostname_3_test(self):
        import pyanaconda.network

        HOSTNAME = 'host3'
        pyanaconda.network.getActiveNetDevs = mock.Mock(return_value=[])
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.socket = mock.Mock()
        pyanaconda.network.socket.gethostname.return_value = HOSTNAME
        anaconda = mock.Mock()
        anaconda.network.hostname = ''

        ret = pyanaconda.network.getDefaultHostname(anaconda)
        self.assertEqual(ret, HOSTNAME)

    def get_default_hostname_4_test(self):
        import pyanaconda.network

        pyanaconda.network.getActiveNetDevs = mock.Mock(return_value=[])
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.socket = mock.Mock()
        pyanaconda.network.socket.gethostname.return_value = ''
        anaconda = mock.Mock()
        anaconda.network.hostname = ''

        ret = pyanaconda.network.getDefaultHostname(anaconda)
        self.assertEqual(ret, self.DEFAULT_HOSTNAME)

    def sanity_check_ip_string_1_test(self):
        import pyanaconda.network

        IPADDR = '10.0.0.5'
        pyanaconda.network.sanityCheckIPString(IPADDR)

    def sanity_check_ip_string_2_test(self):
        import pyanaconda.network

        IPADDR = "ff06:0:0:0:0:0:0:c3"
        pyanaconda.network.sanityCheckIPString(IPADDR)

    def sanity_check_ip_string_3_test(self):
        import pyanaconda.network

        IPADDR = "ff06:.:.:0:0:0:0:c3"
        self.assertRaises(pyanaconda.network.IPError,
            pyanaconda.network.sanityCheckIPString, IPADDR)

    def sanity_check_ip_string_4_test(self):
        import pyanaconda.network
        import socket
        pyanaconda.network.socket.error = socket.error
        pyanaconda.network.socket.inet_pton = mock.Mock(side_effect=socket.error)

        IPADDR = "1.8.64.512"
        self.assertRaises(pyanaconda.network.IPError,
            pyanaconda.network.sanityCheckIPString, IPADDR)

    def sanity_check_ip_string_5_test(self):
        import pyanaconda.network
        import socket
        pyanaconda.network.socket.error = socket.error
        pyanaconda.network.socket.inet_pton = mock.Mock(side_effect=socket.error)

        IPADDR = "top.secret.address"
        self.assertRaises(pyanaconda.network.IPError,
            pyanaconda.network.sanityCheckIPString, IPADDR)

    def has_active_net_dev_1_test(self):
        import pyanaconda.network

        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = \
            pyanaconda.network.isys.NM_STATE_CONNECTED_GLOBAL

        ret = pyanaconda.network.hasActiveNetDev()
        self.assertTrue(ret)
        self.assertTrue(pyanaconda.network.dbus.Interface().Get.called)

    def has_active_net_dev_2_test(self):
        import pyanaconda.network

        pyanaconda.network.dbus = mock.Mock(side_effect=Exception)

        ret = pyanaconda.network.hasActiveNetDev()
        self.assertFalse(ret)

    def has_active_net_dev_3_test(self):
        import pyanaconda.network

        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = self.OK
        pyanaconda.network.isys.NM_STATE_CONNECTED = (self.OK - 5)

        ret = pyanaconda.network.hasActiveNetDev()
        self.assertFalse(ret)

    def networkdevice_read_test(self):
        import pyanaconda.network

        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        ret = nd.read()
        self.assertEqual(ret, 4)
        self.assertEqual(nd.info,
            {'DEVICE': 'eth0', 'HWADDR': '00:11:22:50:55:50',
            'BOOTPROTO': 'dhcp', 'TYPE': 'Ethernet'})

    def networkdevice_clear_test(self):
        import pyanaconda.network

        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.info = {'DEVICE': 'eth0', 'HWADDR': '00:11:22:50:55:50', 'TYPE': 'Ethernet'}
        nd.clear()
        self.assertEqual(nd.info, {})

    def networkdevice_str_test(self):
        import pyanaconda.network
        pyanaconda.network.arch = mock.Mock()
        pyanaconda.network.arch.isS390.return_value = False

        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.info = {'HWADDR': '00:11:22:50:55:50', 'DEVICE': 'eth0', 'TYPE': 'Ethernet'}
        self.assertIn('DEVICE="eth0"', str(nd))
        self.assertIn('TYPE="Ethernet"', str(nd))

    def networkdevice_load_ifcfg_file_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.loadIfcfgFile()
        self.assertFalse(nd._dirty)
        self.assertEqual(nd.info,
            {'DEVICE': 'eth0', 'HWADDR': '00:11:22:50:55:50',
            'TYPE': 'Ethernet', 'BOOTPROTO': 'dhcp'})

    def networkdevice_write_ifcfg_file_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.info = {'HWADDR': '66:55:44:33:22:11', 'DEVICE': 'eth1', 'TYPE': 'Ethernet'}
        nd._dirty = True
        nd.writeIfcfgFile()
        self.assertIn('DEVICE="eth1"\n', self.fs[self.DEV_FILE])
        self.assertIn('HWADDR="66:55:44:33:22:11"', self.fs[self.DEV_FILE])
        self.assertIn('TYPE="Ethernet"', self.fs[self.DEV_FILE])

    def networkdevice_set_1_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.set(('key', 'value'))
        self.assertEqual(nd.info, {'KEY': 'value'})
        self.assertTrue(nd._dirty)

    def networkdevice_set_2_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.set(('key', 'value'))
        nd.set(('key', 'other_value'))
        self.assertEqual(nd.info, {'KEY': 'other_value'})
        self.assertTrue(nd._dirty)

    def networkdevice_set_3_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.set(('key', 'value'))
        nd._dirty = False
        nd.set(('key', 'other_value'))
        self.assertEqual(nd.info, {'KEY': 'other_value'})
        self.assertTrue(nd._dirty)

    def networkdevice_set_gateway_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.setGateway('10.0.0.1')
        self.assertEqual(nd.info, {'GATEWAY': '10.0.0.1'})
        self.assertTrue(nd._dirty)

    def networkdevice_set_gateway_ipv6_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.setGateway('fe80::5675:d0ff:feac:4d3f')
        self.assertEqual(nd.info, {'IPV6_DEFAULTGW': 'fe80::5675:d0ff:feac:4d3f'})
        self.assertTrue(nd._dirty)

    def networkdevice_set_dns_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.setDNS('10.0.0.1, 10.0.0.2')
        self.assertEqual(nd.info, {'DNS1': '10.0.0.1'})
        self.assertEqual(nd.info, {'DNS2': '10.0.0.2'})
        self.assertTrue(nd._dirty)

    def networkdevice_keyfile_path_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        ret = nd.keyfilePath
        self.assertEqual(ret, self.DEV_KEY_FILE)

    def networkdevice_write_wepkey_file_1_test(self):
        import pyanaconda.network
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.wepkey = False
        ret = nd.writeWepkeyFile()
        self.assertFalse(ret)

    def networkdevice_write_wepkey_file_2_test(self):
        import pyanaconda.network
        TMP_FILE = '/tmp/wep.key'
        TMP_DIR = '/tmp/wepkeyfiles'
        pyanaconda.network.tempfile = mock.Mock()
        pyanaconda.network.tempfile.mkstemp.return_value = (88, TMP_FILE)
        pyanaconda.network.os = mock.Mock()
        pyanaconda.network.os.path = os.path
        pyanaconda.network.shutil = mock.Mock()

        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.iface = self.DEVICE
        nd.wepkey = '12345'

        nd.writeWepkeyFile(dir=TMP_DIR)
        self.assertEqual(pyanaconda.network.os.write.call_args[0], (88, 'KEY1=12345\n'))
        self.assertEqual(pyanaconda.network.shutil.move.call_args[0],
            (TMP_FILE, '%s/keys-%s' % (TMP_DIR, self.DEVICE)))

    def network_nm_controlled_devices_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        pyanaconda.network.Network.setNMControlledDevices = self.setNMControlledDevices_backup
        nw.setNMControlledDevices()
        self.assertEqual(nw.netdevices['dev'].method_calls,
            [('set', (('NM_CONTROLLED', 'yes'),), {})])

    def network_nm_controlled_devices_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        pyanaconda.network.Network.setNMControlledDevices = self.setNMControlledDevices_backup
        nw.setNMControlledDevices([''])
        self.assertEqual(nw.netdevices['dev'].method_calls,
            [('set', (('NM_CONTROLLED', 'no'),), {})])

    def network_write_ks_test(self):
        import pyanaconda.network
        TMPFILE = '/tmp/networkKS'
        f = self.fs.open(TMPFILE, 'w')

        nw = pyanaconda.network.Network()
        nw.netdevices[self.DEVICE] = pyanaconda.network.NetworkDevice(
            self.NETSCRIPTSDIR, self.DEVICE)
        nw.netdevices[self.DEVICE].loadIfcfgFile()
        nw.writeKS(f)
        f.close()

        self.assertEqual(self.fs[TMPFILE],
            'network --device eth0 --bootproto dhcp --noipv6\n')

    def network_wait_for_connection_1_test(self):
        import pyanaconda.network
        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = \
            pyanaconda.network.isys.NM_STATE_CONNECTED_GLOBAL

        ret = pyanaconda.network.waitForConnection()
        self.assertTrue(ret)

    def network_wait_for_connection_2_test(self):
        import pyanaconda.network
        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = self.OK-5
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.NM_STATE_CONNECTED = self.OK
        pyanaconda.network.time.sleep = mock.Mock()

        ret = pyanaconda.network.waitForConnection()
        self.assertFalse(ret)

    def network_bring_up_test(self):
        import pyanaconda.network
        pyanaconda.network.Network.write = mock.Mock()
        pyanaconda.network.waitForConnection = mock.Mock()

        nw = pyanaconda.network.Network()
        nw.bringUp()
        self.assertTrue(pyanaconda.network.Network.write.called)
        self.assertTrue(pyanaconda.network.waitForConnection.called)

    def iface_for_host_ip_test(self):
        import pyanaconda.network
        pyanaconda.network.arch = mock.Mock()
        pyanaconda.network.arch.execWithCapture.return_value = \
            "10.0.0.2 dev eth0  src 10.0.0.1"

        ret = pyanaconda.network.ifaceForHostIP('10.0.0.2')
        self.assertEqual(ret, 'eth0')
