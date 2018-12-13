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

    def nm_check_ip_address_test(self,):
        good_IPv4_tests = [
                '1.2.3.4',
                '0.0.0.0',
                '10.20.30.40',
                '255.255.255.255',
                '249.249.249.249'
                ]
        good_IPv6_tests = [
                '0000:0000:0000:0000:0000:0000:0000:0000',
                '0000:0000:0000:0000:0000:0000:1.2.3.4',
                '::a:b:c:d:e:f:1',
                '::a:b:c:d:e:255.255.255.255',
                '1::a:b:c:d:e:f',
                '1::a:b:c:d:255.255.255.255',
                '1:12::a:b:c:d:e',
                '1:12::a:b:c:10.20.30.40',
                '12::a:b:c:d:e',
                '12::a:b:c:10.20.30.40',
                '1:12:123::a:b:c:d',
                '1:12:123::a:b:100.200.250.249',
                '12:123::a:b:c:d',
                '12:123::a:b:100.200.250.249',
                '123::a:b:c:d',
                '123::a:b:100.200.250.249',
                '::a:b:c:d',
                '::a:b:100.200.250.249',
                '1:12:123:1234::a:b:c',
                '1:12:123:1234::a:1.20.30.99',
                '12:123:1234::a:b:c',
                '12:123:1234::a:1.20.30.99',
                '123:1234::a:b:c',
                '123:1234::a:1.20.30.99',
                '1234::a:b:c',
                '1234::a:1.20.30.99',
                '::a:b:c',
                '::a:1.20.30.99',
                '1:12:123:1234:abcd::a:b',
                '1:12:123:1234:abcd::0.0.0.0',
                '12:123:1234:abcd::a:b',
                '12:123:1234:abcd::0.0.0.0',
                '123:1234:abcd::a:b',
                '123:1234:abcd::0.0.0.0',
                '1234:abcd::a:b',
                '1234:abcd::0.0.0.0',
                'abcd::a:b',
                'abcd::0.0.0.0',
                '::a:b',
                '::0.0.0.0',
                '1:12:123:1234:dead:beef::aaaa',
                '12:123:1234:dead:beef::aaaa',
                '123:1234:dead:beef::aaaa',
                '1234:dead:beef::aaaa',
                'dead:beef::aaaa',
                'beef::aaaa',
                '::aaaa',
                '::'
                ]

        bad_IPv4_tests = [
                '1.2.3.',
                '1.2.3',
                '256.2.3.4',
                'a.b.c.d',
                '1.2.3.400'
                '....',
                '1..2.3'
                ]
        bad_IPv6_tests = [
                # Too many bits
                '0000:0000:0000:0000:0000:0000:0000:0000:0000'
                '0000:0000:0000:0000:0000:0000:0000:1.2.3.4',
                '0000:0000:0000:0000:0000:0000:1.2.3.4.5',
                # Not enough bits
                '0000:0000:0000:0000:0000:0000:0000',
                '0000:0000:0000:0000:0000:1.2.3.4',
                # zero-length contractions
                '0000::0000:0000:0000:0000:0000:1.2.3.4',
                '0000:0000::0000:0000:0000:0000:1.2.3.4',
                '0000:0000:0000::0000:0000:0000:1.2.3.4',
                '0000:0000:0000:0000::0000:0000:1.2.3.4',
                '0000:0000:0000:0000:0000::0000:1.2.3.4',
                '0000:0000:0000:0000:0000:0000::1.2.3.4',
                '123::4567:89:a:bcde:f0f0:aaaa:8',
                '123:4567::89:a:bcde:f0f0:aaaa:8',
                '123:4567:89::a:bcde:f0f0:aaaa:8',
                '123:4567:89:a:bcde::f0f0:aaaa:8',
                '123:4567:89:a:bcde:f0f0::aaaa:8',
                '123:4567:89:a:bcde:f0f0:aaaa::8',
                # too many contractions
                'a::b::c',
                '::a::b',
                'a::b::',
                # invalid numbers
                '00000::0000',
                'defg::',
                '12345::abcd',
                'ffff::0x1e'
                ]

        # test good IPv4
        for i in good_IPv4_tests:
            self.assertTrue(network.check_ip_address(i, version=4))
            self.assertTrue(network.check_ip_address(i))
            self.assertFalse(network.check_ip_address(i, version=6))

        # test bad Ipv4
        for i in bad_IPv4_tests:
            self.assertFalse(network.check_ip_address(i))
            self.assertFalse(network.check_ip_address(i, version=4))
            self.assertFalse(network.check_ip_address(i, version=6))

        # test good IPv6
        for i in good_IPv6_tests:
            self.assertTrue(network.check_ip_address(i, version=6))
            self.assertTrue(network.check_ip_address(i))
            self.assertFalse(network.check_ip_address(i, version=4))

        # test bad IPv6
        for i in bad_IPv6_tests:
            self.assertFalse(network.check_ip_address(i))
            self.assertFalse(network.check_ip_address(i, version=6))
            self.assertFalse(network.check_ip_address(i, version=4))

class NetworkKSDataTests(unittest.TestCase):

    def setUp(self):
        self.ksdata_mock = mock.Mock()
        self.ksdata_mock.network = mock.Mock()

    @patch('pyanaconda.dbus.DBus.get_proxy')
    def update_hostname_data_test(self, proxy_getter):
        proxy = mock.Mock()
        proxy_getter.return_value = proxy

        from pyanaconda.kickstart import AnacondaKSHandler
        handler = AnacondaKSHandler()
        ksdata = self.ksdata_mock

        # network --hostname oldhostname
        # pylint: disable=no-member
        nd = handler.NetworkData(hostname="oldhostname", bootProto="")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        proxy.SetHostname.assert_called_with("newhostname")
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")

        # no network in ks
        ksdata.network.network = []
        network.update_hostname_data(ksdata, "newhostname")
        proxy.SetHostname.assert_called_with("newhostname")
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")

        # network --bootproto dhcp --onboot no --device em1 --hostname oldhostname
        # pylint: disable=no-member
        nd = handler.NetworkData(bootProto="dhcp", onboot="no", device="em1", hostname="oldhostname")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        proxy.SetHostname.assert_called_with("newhostname")
        # network --bootproto dhcp --onboot no --device em1 --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "newhostname")
        self.assertEqual(len(ksdata.network.network), 1)

        # network --bootproto dhcp --onboot no --device em1
        # pylint: disable=no-member
        nd = handler.NetworkData(bootProto="dhcp", onboot="no", device="em1")
        ksdata.network.network = [nd]
        network.update_hostname_data(ksdata, "newhostname")
        proxy.SetHostname.assert_called_with("newhostname")
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
        proxy.SetHostname.assert_called_with("newhostname")
        # network --bootproto dhcp --onboot no --device em1
        # network --hostname newhostname
        self.assertEqual(ksdata.network.network[0].hostname, "")
        self.assertEqual(ksdata.network.network[1].hostname, "newhostname")

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
                set(["rd.iscsi.ibft"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "ibft",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
                network.dracutBootArguments("em1", ifcfg, ""),
                set(["rd.iscsi.ibft"]))

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

    @patch("blivet.arch.is_s390", lambda: True)
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
