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

from pyanaconda.modules.network.nm_client import get_slaves_from_connections, \
    get_dracut_arguments_from_connection

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM


class NMClientTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _get_mock_objects_from_attrs(self, obj_attrs):
        objects = []
        for attrs in obj_attrs:
            obj = Mock()
            obj.configure_mock(**attrs)
            objects.append(obj)
        return objects

    @patch("pyanaconda.modules.network.nm_client.get_iface_from_connection")
    def get_slaves_from_connections_test(self, get_iface_from_connection):
        nm_client = Mock()

        ENS3_UUID = "50f1ddc3-cfa5-441d-8afe-729213f5ca92"
        ENS7_UUID = "d9e90dce-93bb-4c30-be16-8f4e77744742"
        ENS8_UUID = "12740d58-c17f-4e8a-a449-2affc6298853"
        ENS11_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140a9"
        TEAM1_UUID = "39ba5d2f-90d1-4bc0-b212-57f643aa7ec1"

        cons_specs = [
            {
                "get_setting_connection.return_value.get_slave_type.return_value": "",
                "get_setting_connection.return_value.get_master.return_value": "",
                "get_uuid.return_value": ENS3_UUID,
            },
            {
                "get_setting_connection.return_value.get_slave_type.return_value": "team",
                "get_setting_connection.return_value.get_master.return_value": "team0",
                "get_uuid.return_value": ENS7_UUID,
            },
            {
                "get_setting_connection.return_value.get_slave_type.return_value": "team",
                "get_setting_connection.return_value.get_master.return_value": "team0",
                "get_uuid.return_value": ENS8_UUID,
            },
            {
                "get_setting_connection.return_value.get_slave_type.return_value": "team",
                "get_setting_connection.return_value.get_master.return_value": TEAM1_UUID,
                "get_uuid.return_value": ENS11_UUID,
            },
        ]
        cons = self._get_mock_objects_from_attrs(cons_specs)
        nm_client.get_connections.return_value = cons

        uuid_to_iface = {
            ENS3_UUID: "ens3",
            ENS7_UUID: "ens7",
            ENS8_UUID: "ens8",
            ENS11_UUID: "ens11",
        }
        get_iface_from_connection.side_effect = lambda nm_client, uuid: uuid_to_iface[uuid]

        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "team", []),
            set()
        )
        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "bridge", ["bridge0"]),
            set()
        )
        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "team", ["team2"]),
            set()
        )
        # Matching of any specification is enough
        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "team", ["team_nonexisting", TEAM1_UUID]),
            set([("ens11", ENS11_UUID)])
        )
        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "team", ["team0"]),
            set([("ens7", ENS7_UUID), ("ens8", ENS8_UUID)])
        )
        self.assertSetEqual(
            get_slaves_from_connections(nm_client, "team", [TEAM1_UUID]),
            set([("ens11", ENS11_UUID)])
        )

    @patch("pyanaconda.modules.network.nm_client.get_connections_available_for_iface")
    @patch("pyanaconda.modules.network.nm_client.get_slaves_from_connections")
    @patch("pyanaconda.modules.network.nm_client.is_s390")
    def get_dracut_arguments_from_connection_test(self, is_s390, get_slaves_from_connections_mock,
                                                  get_connections_available_for_iface):
        nm_client = Mock()

        CON_UUID = "44755f4c-ee12-45b4-ba5e-e10f83de51af"

        # ibft connection
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_wired.return_value": None,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "", "10.34.39.2",
                                                 "my.host.name", ibft=True),
            set(["rd.iscsi.ibft"])
        )

        # ibft connection on s390 with missing s390 options
        is_s390.return_value = True
        wired_setting_attrs = {
            "get_s390_nettype.return_value": "",
            "get_s390_subchannels.return_value": "",
            "get_s390_options.return_value": "",
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]

        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_wired.return_value": wired_setting,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "", "10.34.39.2",
                                                 "my.host.name", ibft=True),
            set(["rd.iscsi.ibft"])
        )

        # ibft connection on s390 with s390 options
        is_s390.return_value = True
        wired_setting_attrs = {
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": "0.0.0900,0.0.0901,0.0.0902",
            "get_s390_options.return_value": {"layer2": "1",
                                              "portname": "FOOBAR",
                                              "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]

        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_wired.return_value": wired_setting,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "", "10.34.39.2",
                                                 "my.host.name", ibft=True),
            set(["rd.iscsi.ibft",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])
        )

        # IPv4 config auto, IPv6 config auto, mac address specified
        is_s390.return_value = False
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        ip6_config_attrs = {
            "get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
        }
        ip6_config = self._get_mock_objects_from_attrs([ip6_config_attrs])[0]
        wired_setting_attrs = {
            "get_mac_address.return_value": "11:11:11:11:11:AA",
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_ip6_config.return_value": ip6_config,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # IPv4 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens3", "10.34.39.2",
                                                 "my.host.name", ibft=False),
            set(["ip=ens3:dhcp",
                 "ifname=ens3:11:11:11:11:11:aa"])
        )
        # IPv6 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                 "my.host.name", ibft=False),
            set(["ip=ens3:auto6",
                 "ifname=ens3:11:11:11:11:11:aa"])
        )

        # IPv4 config static, mac address not specified, s390
        is_s390.return_value = True
        address_attrs = {
            "get_address.return_value": "10.34.39.44",
            "get_prefix.return_value": 24,
        }
        address = self._get_mock_objects_from_attrs([address_attrs])[0]
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_MANUAL,
            "get_num_addresses.return_value": 1,
            "get_address.return_value": address,
            "get_gateway.return_value": "10.34.39.2",
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": "0.0.0900,0.0.0901,0.0.0902",
            "get_s390_options.return_value": {"layer2": "1",
                                              "portname": "FOOBAR",
                                              "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens4", "10.40.49.4",
                                                 "my.host.name", ibft=False),
            set(["ip=10.34.39.44::10.34.39.2:255.255.255.0:my.host.name:ens4:none",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])
        )

        # IPv6 config dhcp
        is_s390.return_value = False
        ip6_config_attrs = {
            "get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_DHCP,
        }
        ip6_config = self._get_mock_objects_from_attrs([ip6_config_attrs])[0]
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip6_config.return_value": ip6_config,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                 "my.host.name", ibft=False),
            set(["ip=ens3:dhcp6"])
        )

        # IPv6 config manual
        is_s390.return_value = False
        address_attrs = {
            "get_address.return_value": "2001::5",
            "get_prefix.return_value": 64,
        }
        address = self._get_mock_objects_from_attrs([address_attrs])[0]
        ip6_config_attrs = {
            "get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_MANUAL,
            "get_num_addresses.return_value": 1,
            "get_address.return_value": address,
            "get_gateway.return_value": "2001::1",
        }
        ip6_config = self._get_mock_objects_from_attrs([ip6_config_attrs])[0]
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip6_config.return_value": ip6_config,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                 "my.host.name", ibft=False),
            set(["ip=[2001::5/64]::[2001::1]::my.host.name:ens3:none"])
        )

        # IPv4 config auto, team
        is_s390.return_value = False
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        cons_attrs = [
            # team master
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": None,
                "get_connection_type.return_value": "team",
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        get_slaves_from_connections_mock.return_value = set([
            ("ens7", "6a6b4586-1e4c-451f-87fa-09b059ceba3d"),
            ("ens8", "ac4a0747-d1ea-4119-903b-18f3adad9116"),
        ])
        # IPv4 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "team0", "10.34.39.2",
                                                 "my.host.name", ibft=False),
            set(["ip=team0:dhcp",
                 "team=team0:ens7,ens8"])
        )

        # IPv4 config auto, vlan, s390, parent specified by interface name
        is_s390.return_value = True
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        setting_vlan_attrs = {
            "get_parent.return_value": "ens11",
        }
        setting_vlan = self._get_mock_objects_from_attrs([setting_vlan_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": None,
                "get_connection_type.return_value": "vlan",
                "get_setting_vlan.return_value": setting_vlan,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # Mock parent connection
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": "0.0.0900,0.0.0901,0.0.0902",
            "get_s390_options.return_value": {"layer2": "1",
                                              "portname": "FOOBAR",
                                              "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        parent_cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        parent_cons = self._get_mock_objects_from_attrs(parent_cons_attrs)
        get_connections_available_for_iface.return_value = parent_cons
        # IPv4 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens11.111", "10.34.39.2",
                                                 "my.host.name", ibft=False),
            set(["ip=ens11.111:dhcp",
                 "vlan=ens11.111:ens11",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])
        )

        # IPv4 config auto, vlan, parent specified by connection uuid
        VLAN_PARENT_UUID = "5e6ead30-d133-4c8c-ba59-818c5ced6a7c"
        is_s390.return_value = False
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        setting_vlan_attrs = {
            "get_parent.return_value": VLAN_PARENT_UUID,
        }
        setting_vlan = self._get_mock_objects_from_attrs([setting_vlan_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": None,
                "get_connection_type.return_value": "vlan",
                "get_setting_vlan.return_value": setting_vlan,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # Mock parent connection
        parent_cons_attrs = [
            {
                "get_interface_name.return_value": "ens12",
            },
        ]
        parent_con = self._get_mock_objects_from_attrs(parent_cons_attrs)[0]
        nm_client.get_connection_by_uuid.return_value = parent_con
        # IPv4 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens12.111", "10.34.39.2",
                                                 "my.host.name", ibft=False),
            set(["ip=ens12.111:dhcp",
                 "vlan=ens12.111:ens12"])
        )

        # IPv4 config auto, vlan, parent specified by connection uuid, s390 (we
        # need the parent connection in s390 case, not only parent iface)
        is_s390.return_value = True
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        setting_vlan_attrs = {
            "get_parent.return_value": "ens13",
        }
        setting_vlan = self._get_mock_objects_from_attrs([setting_vlan_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": None,
                "get_connection_type.return_value": "vlan",
                "get_setting_vlan.return_value": setting_vlan,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # Mock parent connection
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": "0.0.0900,0.0.0901,0.0.0902",
            "get_s390_options.return_value": {"layer2": "1",
                                              "portname": "FOOBAR",
                                              "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        parent_cons_attrs = [
            {
                # On s390 with net.ifnames=0 the iface is identified by NAME, not DEVICE
                "get_interface_name.return_value": None,
                "get_id.return_value": "ens13",
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": "802-3-ethernet",
            },
        ]
        parent_cons = self._get_mock_objects_from_attrs(parent_cons_attrs)
        nm_client.get_connection_by_uuid.return_value = parent_con
        # IPv4 target
        self.assertSetEqual(
            get_dracut_arguments_from_connection(nm_client, con, "ens13.111", "10.34.39.2",
                                                 "my.host.name", ibft=False),
            set(["ip=ens13.111:dhcp",
                 "vlan=ens13.111:ens13",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])
        )
