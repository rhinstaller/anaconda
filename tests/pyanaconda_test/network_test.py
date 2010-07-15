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
        self.controlWireless_backup = pyanaconda.network.Network.controlWireless
        pyanaconda.network.Network.controlWireless = mock.Mock()
        self.setNMControlledDevices_backup = pyanaconda.network.Network.setNMControlledDevices
        pyanaconda.network.Network.setNMControlledDevices = mock.Mock()
        pyanaconda.network.Network.netdevices = {}
          
    def tearDown(self):
        self.tearDownModules()

    def sanity_check_hostname_1_test(self):
        import pyanaconda.network
        ret = pyanaconda.network.sanityCheckHostname('desktop')
        self.assertEqual(ret, None)

    def sanity_check_hostname_2_test(self):
        import pyanaconda.network
        ret = pyanaconda.network.sanityCheckHostname('')
        self.assertEqual(ret, None)

    def sanity_check_hostname_3_test(self):
        import pyanaconda.network
        ret = pyanaconda.network.sanityCheckHostname('c'*256)
        self.assertNotEqual(ret, None)

    def sanity_check_hostname_4_test(self):
        import pyanaconda.network
        ret = pyanaconda.network.sanityCheckHostname('_asf')
        self.assertNotEqual(ret, None)

    def sanity_check_hostname_5_test(self):
        import pyanaconda.network
        ret = pyanaconda.network.sanityCheckHostname('a?f')
        self.assertNotEqual(ret, None)

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
        pyanaconda.network.dbus.Interface().Get.return_value = self.OK
        pyanaconda.network.isys.NM_STATE_CONNECTED = self.OK
        
        ret = pyanaconda.network.hasActiveNetDev()
        self.assertTrue(ret)

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
    
    #def get_active_net_devs_test(self):
    #    pass

    ##
    ## NetworkDevice class tests
    ##

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
        pyanaconda.network.iutil = mock.Mock()
        pyanaconda.network.iutil.isS390.return_value = False
        
        nd = pyanaconda.network.NetworkDevice(self.NETSCRIPTSDIR, self.DEVICE)
        nd.info = {'HWADDR': '00:11:22:50:55:50', 'DEVICE': 'eth0', 'TYPE': 'Ethernet'}
        self.assertTrue(str(nd).startswith('DEVICE="eth0"'))

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
        self.assertEqual(self.fs[self.DEV_FILE],    
            'DEVICE="eth1"\nHWADDR="66:55:44:33:22:11"\nTYPE="Ethernet"\n')
    
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
           
    #def networkdevice_used_by_fcoe_test(self):
    #    pass
    
    #dev networkdevice_used_by_root_on_iscsi_test(self):
    #    pass
    
    #def networkdevice_used_by_iscsi_test(self):
    #    pass
    
    ##
    ## Network class tests
    ##
    
    #def network_update_test(self):
    #    pass
    
    def network_get_device_test(self):
        import pyanaconda.network       
        
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = 'device'
        ret = nw.getDevice('dev')
        self.assertEqual(ret, 'device')
        
    def network_get_ks_device_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.ksdevice = None
        ret = nw.getKSDevice()
        self.assertEqual(ret, None)
    
    def network_get_ks_device_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.ksdevice = 'ksdev'
        ret = nw.getKSDevice()
        self.assertEqual(ret, None)
    
    def network_get_ks_device_3_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['ksdev'] = 'device'
        nw.ksdevice = 'ksdev'
        ret = nw.getKSDevice()
        self.assertEqual(ret, 'device')
    
    def network_set_hostname_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.setHostname('DESKTOP')
        self.assertEqual(nw.hostname, 'DESKTOP')
        
    def network_set_dns_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        nw.setDNS('10.0.0.1, 10.0.0.2', 'dev')
        self.assertEqual(nw.netdevices['dev'].method_calls, 
            [('set', (('DNS1', '10.0.0.1'),), {}), 
            ('set', (('DNS2', '10.0.0.2'),), {})]
        )
        
    def network_set_gateway_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['eth0'] = mock.Mock()
        nw.setGateway('10.0.0.1', 'eth0')
        self.assertEqual(pyanaconda.network.Network.netdevices['eth0'].method_calls,
            [('set', (('GATEWAY', '10.0.0.1'),), {})])
    
    def network_lookup_hostname_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.hostname = None
        ret = nw.lookupHostname()
        self.assertEqual(ret, None)
    
    def network_lookup_hostname_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.hostname = 'desktop'
        pyanaconda.network.hasActiveNetDev = mock.Mock(return_value=False)
        ret = nw.lookupHostname()
        self.assertEqual(ret, None)
    
    def network_lookup_hostname_3_test(self):
        import pyanaconda.network
        pyanaconda.network.socket.getaddrinfo.return_value = \
            [(0, 0, 0, 0, ('10.1.1.1', 0))]
        
        nw = pyanaconda.network.Network()
        nw.hostname = 'desktop'
        pyanaconda.network.hasActiveNetDev = mock.Mock(return_value=True)
        ret = nw.lookupHostname()
        self.assertEqual(ret, '10.1.1.1')
    
    def network_write_ifcfg_files_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        nw.writeIfcfgFiles()
        self.assertTrue(nw.netdevices['dev'].writeIfcfgFile.called)
        
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
    
    def network_update_active_devices_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        nw.updateActiveDevices()
        self.assertEqual(nw.netdevices['dev'].method_calls, 
            [('set', (('ONBOOT', 'yes'),), {})])
        
    def network_update_active_devices_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        nw.updateActiveDevices([''])
        self.assertEqual(nw.netdevices['dev'].method_calls, 
            [('set', (('ONBOOT', 'no'),), {})])
            
    def network_get_on_boot_controlled_ifaces_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        ret = nw.getOnbootControlledIfaces()
        self.assertEqual(ret, [])
        
    def network_get_on_boot_controlled_ifaces_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        a = mock.Mock()
        a.get.return_value = "yes"
        nw.netdevices = {'dev': a}
        ret = nw.getOnbootControlledIfaces()
        self.assertEqual(ret, ['dev'])
        
    def network_update_ifcfg_ssid_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': mock.Mock()}
        ret = nw.updateIfcfgsSSID({'dev': ['net_essid']})
        self.assertEqual(nw.netdevices['dev'].method_calls[0],
            ('set', (('ESSID', 'net_essid'),), {}))
        self.assertEqual(nw.netdevices['dev'].method_calls[1],
            ('writeIfcfgFile', (), {}))
    
    #def network_get_ssids_test(self):
    #    pass
    
    def network_select_preferred_ssids_1_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        nw.netdevices['dev'].get.return_value = 'some_essid'
        dev_ssid = {'dev': ['some_essid']}
        nw.selectPreferredSSIDs(dev_ssid)
        self.assertEqual(dev_ssid, {'dev': ['some_essid']})
    
    def network_select_preferred_ssids_2_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        nw.netdevices['dev'].get.return_value = 'some_essid'
        dev_ssid = {'dev': ['some_essid', 'other']}
        nw.selectPreferredSSIDs(dev_ssid)
        self.assertEqual(dev_ssid, {'dev': ['some_essid']})
    
    def network_select_preferred_ssids_3_test(self):
        import pyanaconda.network
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        nw.netdevices['dev'].get.return_value = 'some_essid'
        dev_ssid = {'dev': ['other', 'foo']}
        nw.selectPreferredSSIDs(dev_ssid)
        self.assertEqual(dev_ssid, {'dev': ['other', 'foo']})
        
    def network_control_wireless_test(self):
        import pyanaconda.network
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.isWirelessDevice.return_value = True
        nw = pyanaconda.network.Network()
        pyanaconda.network.Network.controlWireless = self.controlWireless_backup
        nw.netdevices['dev'] = mock.Mock()
        nw.controlWireless()
        self.assertEqual(nw.netdevices['dev'].method_calls,
            [('set', (('NM_CONTROLLED', 'yes'),), {})])
        
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
    
    def network_has_name_server_1_test(self):
        import pyanaconda.network
        hash = {'foo':'', 'bar':''}
        
        nw = pyanaconda.network.Network()
        ret = nw.hasNameServers(hash)
        self.assertFalse(ret)
    
    def network_has_name_server_2_test(self):
        import pyanaconda.network
        hash = {'foo':'', 'bar':'', 'dnsserver':''}
        
        nw = pyanaconda.network.Network()
        ret = nw.hasNameServers(hash)
        self.assertTrue(ret)
        
    def network_has_wireless_dev_1_test(self):
        import pyanaconda.network
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.isWirelessDevice.return_value = True

        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': ''}
        ret = nw.hasWirelessDev()
        self.assertTrue(ret)
        
    def network_has_wireless_dev_2_test(self):
        import pyanaconda.network
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.isWirelessDevice.return_value = False

        nw = pyanaconda.network.Network()
        nw.netdevices = {'dev': ''}
        ret = nw.hasWirelessDev()
        self.assertFalse(ret)
    
    #def network_copy_file_to_path_test(self):
    #    pass
    
    def network_copy_config_to_path_test(self):
        import pyanaconda.network
        pyanaconda.network.Network._copyFileToPath = mock.Mock()
        
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        nw.netdevices['dev'].path = self.DEV_FILE
        nw.netdevices['dev'].keyfilePath = self.DEV_KEY_FILE
        ret = nw.copyConfigToPath('')
        self.assertEqual(pyanaconda.network.Network._copyFileToPath.call_args_list,
            [(('/tmp/etc/sysconfig/network-scripts/ifcfg-eth0', ''), {}), 
             (('/tmp/etc/sysconfig/network-scripts/keys-eth0', ''), {}), 
             (('/etc/dhcp/dhclient-dev.conf', ''), {}), 
             (('/tmp/etc/sysconfig/network', ''), {'overwrite': 0}), 
             (('/etc/resolv.conf', ''), {'overwrite': 0}), 
             (('/etc/udev/rules.d/70-persistent-net.rules', ''), {'overwrite': 0})]
        )
    
    def network_disable_nm_for_storage_devices_test(self):
        import pyanaconda.network
        pyanaconda.network.NetworkDevice = mock.Mock()
        pyanaconda.network.os = mock.Mock()
        pyanaconda.network.os.access.return_value = True
        
        nw = pyanaconda.network.Network()
        nw.netdevices['dev'] = mock.Mock()
        anaconda= mock.Mock()
        
        nw.disableNMForStorageDevices(anaconda, '')
        self.assertEqual(pyanaconda.network.NetworkDevice.call_args_list, 
             [(('/tmp/etc/sysconfig/network-scripts', 'dev'), {})])
        self.assertEqual(pyanaconda.network.NetworkDevice().method_calls, 
            [('loadIfcfgFile', (), {}), 
             ('set', (('NM_CONTROLLED', 'no'),), {}), 
             ('writeIfcfgFile', (), {})]
         )
         
    def network_write_test(self):
        import pyanaconda.network
        pyanaconda.network.shutil = mock.Mock()
        pyanaconda.network.os = mock.Mock()
        pyanaconda.network.os.path.isfile.return_value = True
        self.fs.open(self.NETWORKCONFFILE, 'w')
        
        device = pyanaconda.network.NetworkDevice(
            self.NETSCRIPTSDIR, self.DEVICE)
        device.loadIfcfgFile()
        
        nw = pyanaconda.network.Network()
        nw.domains = ['localdomain']
        nw.netdevices[self.DEVICE] = device
        nw.write()
        
        self.assertEqual(self.fs['%s.new' % self.NETWORKCONFFILE], 
            'NETWORKING=yes\nHOSTNAME=localhost.localdomain\n')
        
    #def network_wait_for_devices_activation_test(self):
    #    pass
    
    def network_wait_for_connection_1_test(self):
        import pyanaconda.network
        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = self.OK
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.NM_STATE_CONNECTED = self.OK
        
        nw = pyanaconda.network.Network()
        ret = nw.waitForConnection()
        self.assertTrue(ret)
        
    def network_wait_for_connection_2_test(self):
        import pyanaconda.network
        pyanaconda.network.dbus = mock.Mock()
        pyanaconda.network.dbus.Interface().Get.return_value = self.OK-5
        pyanaconda.network.isys = mock.Mock()
        pyanaconda.network.isys.NM_STATE_CONNECTED = self.OK
        pyanaconda.network.time.sleep = mock.Mock()
        
        nw = pyanaconda.network.Network()
        ret = nw.waitForConnection()
        self.assertFalse(ret)
        
    def network_bring_up_test(self):
        import pyanaconda.network
        pyanaconda.network.Network.write = mock.Mock()
        pyanaconda.network.Network.waitForConnection = mock.Mock()
        
        nw = pyanaconda.network.Network()
        nw.bringUp()
        self.assertTrue(pyanaconda.network.Network.write.called)
        self.assertTrue(pyanaconda.network.Network.waitForConnection.called)
    
    #def network_dracut_setup_string_test(self):
    #    import pyanaconda.network
    #    pass
    
    #def get_ssids_test(self):
    #    import pyanaconda.network
    #    pass
    
    def iface_for_host_ip_test(self):
        import pyanaconda.network
        pyanaconda.network.iutil = mock.Mock()
        pyanaconda.network.iutil.execWithCapture.return_value = \
            "10.0.0.2 dev eth0  src 10.0.0.1"
        
        ret = pyanaconda.network.ifaceForHostIP('10.0.0.2')
        self.assertEqual(ret, 'eth0')
        
