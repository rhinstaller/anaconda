#
# Copyright (C) 2019  Red Hat, Inc.
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
#
import unittest
from mock import Mock, patch

from pyanaconda.modules.network.ifcfg import get_dracut_arguments_from_ifcfg

class IfcfgTestCase(unittest.TestCase):
    def ifcfg_mock(self, settings):
        def get(value):
            return settings.get(value.upper(), "")
        m = Mock()
        m.get = get
        return m

    def get_dracut_arguments_from_ifcfg_test(self):
        ifcfg = self.ifcfg_mock({"BOOTPROTO": "ibft"})
        nm_client = Mock()
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "", None),
            set(["rd.iscsi.ibft"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "ibft",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "", None),
            set(["rd.iscsi.ibft"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "dhcp"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=em1:dhcp"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "dhcp",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=em1:dhcp", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "PREFIX": "24"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=10.34.102.233::10.34.102.254:255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", None),
            set(["ip=10.34.102.233:::255.255.255.0::em1:none"]))

        ifcfg = self.ifcfg_mock({"BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "10.34.102.77", "node1"),
            set(["ip=10.34.102.233::10.34.102.254:255.255.255.0:node1:em1:none"]))

        ifcfg = self.ifcfg_mock({"DHCPV6C": "yes",
                                 "IPV6_AUTOCONF": "yes"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", None),
            set(["ip=em1:dhcp6"]))

        ifcfg = self.ifcfg_mock({"IPV6_AUTOCONF": "yes"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", None),
            set(["ip=em1:auto6"]))

        ifcfg = self.ifcfg_mock({"IPV6_AUTOCONF": "yes",
                                 "HWADDR": "00:00:00:00:00:00"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", None),
            set(["ip=em1:auto6", "ifname=em1:00:00:00:00:00:00"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", None),
            set(["ip=[2001::4]:::::em1:none"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", "node1"),
            set(["ip=[2001::4]::::node1:em1:none"]))

        ifcfg = self.ifcfg_mock({"IPV6ADDR": "2001::4",
                                 "IPV6_DEFAULTGW": "2001::a"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "em1", "2001::1", None),
            set(["ip=[2001::4]::[2001::a]:::em1:none"]))

    @patch("pyanaconda.modules.network.ifcfg.is_s390", lambda: True)
    def get_dracut_arguments_from_ifcfg_s390_test(self):
        nm_client = Mock()
        ifcfg = self.ifcfg_mock({"NETTYPE": "qeth",
                                 "SUBCHANNELS": "0.0.f5f0,0.0.f5f1,0.0.f5f2",
                                 "OPTIONS": '"layer2=1 portname=OSAPORT"'})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "eth0", "", None),
            set(["rd.znet=qeth,0.0.f5f0,0.0.f5f1,0.0.f5f2,layer2=1,portname=OSAPORT"]))

        ifcfg = self.ifcfg_mock({"NETTYPE": "qeth",
                                 "SUBCHANNELS": "0.0.f5f0,0.0.f5f1,0.0.f5f2",
                                 "OPTIONS": '"layer2=1 portname=OSAPORT"',
                                 "BOOTPROTO": "static",
                                 "IPADDR": "10.34.102.233",
                                 "GATEWAY": "10.34.102.254",
                                 "NETMASK": "255.255.255.0"})
        self.assertEqual(
            get_dracut_arguments_from_ifcfg(nm_client, ifcfg, "eth0", "10.34.102.77", None),
            set(["rd.znet=qeth,0.0.f5f0,0.0.f5f1,0.0.f5f2,layer2=1,portname=OSAPORT",
                 "ip=10.34.102.233::10.34.102.254:255.255.255.0::eth0:none"]))
