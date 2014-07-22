# -*- coding: utf-8 -*-
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>

from pyanaconda import network
import unittest
import mock
from mock import patch

class NetworkTests(unittest.TestCase):

    def default_ks_vlan_interface_name_test(self):
        self.assertEqual(network.default_ks_vlan_interface_name("em1", "171"),
                         "em1.171")

    def bond_options_ksdata_to_dbus_test(self):
        cases = [("mode=802.3ad,miimon=100,xmit_hash_policy=layer2+3,lacp_rate=fast",
                  {"mode":"802.3ad",
                     "miimon":"100",
                     "xmit_hash_policy":"layer2+3",
                     "lacp_rate":"fast"}),
                 ("mode=balance-alb,arp_interval=100,arp_ip_target=192.168.122.1",
                  {"mode":"balance-alb",
                   "arp_interval":"100",
                   "arp_ip_target":"192.168.122.1"}),
                 ("mode=active-backup,primary=eth1,miimon=100,fail_over_mac=2",
                  {"mode":"active-backup",
                   "primary":"eth1",
                   "miimon":"100",
                   "fail_over_mac":"2"}),
                 ("option1=value1,value2;option2=value3",
                  {"option1":"value1,value2",
                   "option2":"value3"}),
                ]
        for bondopts, dbus_dict in cases:
            self.assertEqual(network.bond_options_ksdata_to_dbus(bondopts), dbus_dict)

    def sanityCheckHostname_test(self):

        self.assertFalse(network.sanityCheckHostname("")[0])
        self.assertFalse(network.sanityCheckHostname(None)[0])

        # section length < 64
        self.assertTrue(network.sanityCheckHostname("h"*63)[0])
        self.assertFalse(network.sanityCheckHostname("h"*64)[0])

        # length < 256
        self.assertTrue(network.sanityCheckHostname("section." * 31+"section")[0])
        self.assertFalse(network.sanityCheckHostname("section." * 31+"sectionx")[0])

        self.assertFalse(network.sanityCheckHostname(
            "section.must.be..nonempty.")[0])
        self.assertFalse(network.sanityCheckHostname(
            ".section.must.be.nonempty.")[0])
        self.assertTrue(network.sanityCheckHostname(
            "section.can.contain.only.alphanums.012.or.hyp-hens")[0])
        self.assertFalse(network.sanityCheckHostname(
            "section.can.contain.only.alphanums.012.or.hyp-hens!!!")[0])
        self.assertFalse(network.sanityCheckHostname(
            "section.may.not.start.with.-hyphen")[0])
        self.assertFalse(network.sanityCheckHostname(
            "section.may.not.end.with.hyphen-")[0])

        self.assertTrue(network.sanityCheckHostname("0-0.")[0])
        self.assertTrue(network.sanityCheckHostname("0.")[0])

        self.assertFalse(network.sanityCheckHostname("Lennart's Laptop")[0])

    def prefix2netmask2prefix_test(self):
        lore = [
                (0, "0.0.0.0"),
                (1, "128.0.0.0"),
                (2, "192.0.0.0"),
                (3, "224.0.0.0"),
                (4, "240.0.0.0"),
                (5, "248.0.0.0"),
                (6, "252.0.0.0"),
                (7, "254.0.0.0"),
                (8, "255.0.0.0"),
                (9, "255.128.0.0"),
                (10, "255.192.0.0"),
                (11, "255.224.0.0"),
                (12, "255.240.0.0"),
                (13, "255.248.0.0"),
                (14, "255.252.0.0"),
                (15, "255.254.0.0"),
                (16, "255.255.0.0"),
                (17, "255.255.128.0"),
                (18, "255.255.192.0"),
                (19, "255.255.224.0"),
                (20, "255.255.240.0"),
                (21, "255.255.248.0"),
                (22, "255.255.252.0"),
                (23, "255.255.254.0"),
                (24, "255.255.255.0"),
                (25, "255.255.255.128"),
                (26, "255.255.255.192"),
                (27, "255.255.255.224"),
                (28, "255.255.255.240"),
                (29, "255.255.255.248"),
                (30, "255.255.255.252"),
                (31, "255.255.255.254"),
                (32, "255.255.255.255"),
               ]
        for prefix, netmask in lore:
            self.assertEqual(network.prefix2netmask(prefix), netmask)
            self.assertEqual(network.netmask2prefix(netmask), prefix)

        self.assertEqual(network.prefix2netmask(33), "255.255.255.255")

    @patch("pyanaconda.network.flags.cmdline",
           {"BOOTIF":"01-11-11-11-11-11-11"})
    @patch("pyanaconda.nm.nm_device_perm_hwaddress")
    @patch("pyanaconda.nm.nm_device_carrier",
            lambda dev: dev == "eth1")
    @patch("pyanaconda.nm.nm_devices",
            lambda: ["eth0", "eth1"])
    def nm_ks_spec_to_device_name_test(self, nm_hwaddr_mock):
        def hwaddr_mock(dev):
            h = {"eth0" : "00:00:00:00:00:00",
                 "eth1" : "11:11:11:11:11:11"}
            try:
                mac = h[dev]
            except KeyError:
                raise ValueError
            return mac

        nm_hwaddr_mock.side_effect = hwaddr_mock
        self.assertEqual(network.ks_spec_to_device_name("eth0"), "eth0")
        self.assertEqual(network.ks_spec_to_device_name("eth1"), "eth1")
        self.assertEqual(network.ks_spec_to_device_name("nonexisting"), "nonexisting")
        self.assertEqual(network.ks_spec_to_device_name("link"), "eth1")
        self.assertNotEqual(network.ks_spec_to_device_name("link"), "eth0")
        self.assertEqual(network.ks_spec_to_device_name("00:00:00:00:00:00"), "eth0")
        self.assertNotEqual(network.ks_spec_to_device_name("00:00:00:00:00:00"), "eth1")
        self.assertEqual(network.ks_spec_to_device_name("bootif"), "eth1")
        self.assertNotEqual(network.ks_spec_to_device_name("bootif"), "eth0")

class NetworkKSDataTests(unittest.TestCase):

    def setUp(self):
        self.ksdata_mock = mock.Mock()
        self.ksdata_mock.network = mock.Mock()

    def update_hostname_data_test(self):
        from pyanaconda.kickstart import AnacondaKSHandler
        handler = AnacondaKSHandler()
        ksdata = self.ksdata_mock

        # network --hostname oldhostname
        # pylint: disable=no-member
        nd = handler.NetworkData(hostname="oldhostname", bootProto="")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")

        # no network in ks
        ksdata.network.network = []
        network.update_hostname_data(ksdata, "newhostname")
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")

        # network --bootproto dhcp --onboot no --device em1 --hostname oldhostname
        # pylint: disable=no-member
        nd = handler.NetworkData(bootProto="dhcp", onboot="no", device="em1", hostname="oldhostname")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        # network --bootproto dhcp --onboot no --device em1 --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")
        self.assertEqual(len(ksdata.network.network), 1)

        # network --bootproto dhcp --onboot no --device em1
        # pylint: disable=no-member
        nd = handler.NetworkData(bootProto="dhcp", onboot="no", device="em1")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        # network --bootproto dhcp --onboot no --device em1
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "")
        self.assertEqual(ksdata.network.network[1].hostname, "newhostname")

        # network --bootproto dhcp --onboot no --device em1
        # network --hostname oldhostname
        # pylint: disable=no-member
        nd1 = handler.NetworkData(bootProto="dhcp", onboot="no", device="em1")
        # pylint: disable=no-member
        nd2 = handler.NetworkData(hostname="oldhostname", bootProto="")
        ksdata.network.network = [nd1, nd2]
        network.update_hostname_data(ksdata, "newhostname")
        # network --bootproto dhcp --onboot no --device em1
        # network --hostname newhostname
        self.assertEquals(ksdata.network.network[0].hostname, "")
        self.assertEquals(ksdata.network.network[1].hostname, "newhostname")

class NetworkIfcfgTests(unittest.TestCase):
    def ifcfg_mock(self, settings):
        def get(value):
            return settings.get(value.upper(), "")
        m = mock.Mock()
        m.get = get
        return m

    def dracutBootArguments_test(self):
        ifcfg = self.ifcfg_mock({"BOOTPROTO": "ibft"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, ""),
                set(["ip=ibft"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "ibft",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, ""),
                set(["ip=ibft"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "dhcp"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=em1:dhcp"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "dhcp",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=em1:dhcp", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "PREFIX": "24"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77"),
                set(["ip=10.34.102.233:::255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "10.34.102.77", hostname="node1"),
                set(["ip=10.34.102.233::10.34.102.254:255.255.255.0:node1:em1:none"]))

        ifcfg = self.ifcfg_mock({"DHCPV6C": "yes",
                                 "IPV6_AUTOCONF": "yes"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1"),
                set(["ip=em1:dhcp6"]))

        ifcfg = self.ifcfg_mock({"IPV6_AUTOCONF": "yes"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1"),
                set(["ip=em1:auto6"]))

        ifcfg = self.ifcfg_mock({"IPV6_AUTOCONF": "yes",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1"),
                set(["ip=em1:auto6", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1"),
                set(["ip=[2001::4]:::::em1:none"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1", hostname="node1"),
                set(["ip=[2001::4]::::node1:em1:none"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4",
                                 "IPV6_DEFAULTGW": "2001::a"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, "2001::1"),
                set(["ip=[2001::4]::[2001::a]:::em1:none"]))

    @patch("blivet.arch.isS390", lambda: True)
    def dracutBootArguments_s390_test(self):
        ifcfg = self.ifcfg_mock({"NETTYPE": "qeth",
                                 "SUBCHANNELS": "0.0.f5f0,0.0.f5f1,0.0.f5f2",
                                 "OPTIONS": '"layer2=1 portname=OSAPORT"'})
        self.assertEqual(
                network.dracutBootArguments("eth0", ifcfg, ""),
                set(["rd.znet=qeth,0.0.f5f0,0.0.f5f1,0.0.f5f2,layer2=1,portname=OSAPORT"]))

        ifcfg = self.ifcfg_mock({"NETTYPE": "qeth",
                                 "SUBCHANNELS": "0.0.f5f0,0.0.f5f1,0.0.f5f2",
                                 "OPTIONS": '"layer2=1 portname=OSAPORT"',
                                 "BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
                network.dracutBootArguments("eth0", ifcfg, "10.34.102.77"),
                set(["rd.znet=qeth,0.0.f5f0,0.0.f5f1,0.0.f5f2,layer2=1,portname=OSAPORT",
                     "ip=10.34.102.233::10.34.102.254:255.255.255.0::eth0:none"]))

