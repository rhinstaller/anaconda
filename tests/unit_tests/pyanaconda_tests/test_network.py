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

import unittest

from pyanaconda import network


class NetworkTests(unittest.TestCase):

    def test_is_valid_hostname(self):
        """Test hostname validation."""

        assert not network.is_valid_hostname("")[0]
        assert not network.is_valid_hostname(None)[0]

        # section length < 64
        assert network.is_valid_hostname("h"*63)[0]
        assert not network.is_valid_hostname("h"*64)[0]

        # length < 65
        assert network.is_valid_hostname("section." * 7+"sectionx")[0]
        assert not network.is_valid_hostname("section." * 7+"sectionxx")[0]

        assert not network.is_valid_hostname(
            "section.must.be..nonempty.")[0]
        assert not network.is_valid_hostname(
            ".section.must.be.nonempty.")[0]
        assert network.is_valid_hostname(
            "section.can.contain.only.alphanums.012.or.hyp-hens")[0]
        assert not network.is_valid_hostname(
            "section.can.contain.only.alphanums.012.or.hyp-hens!!!")[0]
        assert not network.is_valid_hostname(
            "section.may.not.start.with.-hyphen")[0]
        assert not network.is_valid_hostname(
            "section.may.not.end.with.hyphen-")[0]

        assert network.is_valid_hostname("0-0.")[0]
        assert network.is_valid_hostname("0.")[0]

        assert not network.is_valid_hostname("Lennart's Laptop")[0]

        assert not network.is_valid_hostname("own.hostname.cannot.end.in.dot.",
                                             local=True)[0]

    def test_prefix2netmask2prefix(self):
        """Test netmask and prefix conversion."""
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
            assert network.prefix_to_netmask(prefix) == netmask
            assert network.netmask_to_prefix(netmask) == prefix

        assert network.prefix_to_netmask(33) == "255.255.255.255"

    def test_nm_check_ip_address(self,):
        """Test IPv4 and IPv6 address checks."""
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
            assert network.check_ip_address(i, version=4)
            assert network.check_ip_address(i)
            assert not network.check_ip_address(i, version=6)

        # test bad Ipv4
        for i in bad_IPv4_tests:
            assert not network.check_ip_address(i)
            assert not network.check_ip_address(i, version=4)
            assert not network.check_ip_address(i, version=6)

        # test good IPv6
        for i in good_IPv6_tests:
            assert network.check_ip_address(i, version=6)
            assert network.check_ip_address(i)
            assert not network.check_ip_address(i, version=4)

        # test bad IPv6
        for i in bad_IPv6_tests:
            assert not network.check_ip_address(i)
            assert not network.check_ip_address(i, version=6)
            assert not network.check_ip_address(i, version=4)

    def test_hostname_from_cmdline(self):
        """Test extraction of hostname from cmdline."""
        cmdline = {"ip": "10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        # ip takes precedence
        cmdline = {"ip": "10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none",
                   "hostname": "hostname_bootopt"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        cmdline = {"ip": "ens3:dhcp"}
        assert network.hostname_from_cmdline(cmdline) == ""
        cmdline = {"ip": "ens3:dhcp:1500"}
        assert network.hostname_from_cmdline(cmdline) == ""
        cmdline = {"ip": "ens3:dhcp",
                   "hostname": "hostname_bootopt"}
        assert network.hostname_from_cmdline(cmdline) == "hostname_bootopt"
        # two ip configurations
        cmdline = {"ip": "ens3:dhcp 10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        # ipv6 configuration
        cmdline = {"ip": "[fd00:10:100::84:5]::[fd00:10:100::86:49]:80:myhostname:ens50:none"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        cmdline = {"ip": "[fd00:10:100::84:5]:::80:myhostname:ens50:none"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        cmdline = {"ip": "[fd00:10:100::84:5]::[fd00:10:100::86:49]:80::ens50:none"}
        assert network.hostname_from_cmdline(cmdline) == ""
        cmdline = {"ip": "[fd00:10:100::84:5]::[fd00:10:100::86:49]:80::ens50:none "
                         "ens3:dhcp 10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none"}
        assert network.hostname_from_cmdline(cmdline) == "myhostname"
        # automatic ip= whith MAC address set
        cmdline = {"ip": "ens3:dhcp::52:54:00:12:34:56"}
        assert network.hostname_from_cmdline(cmdline) == ""
