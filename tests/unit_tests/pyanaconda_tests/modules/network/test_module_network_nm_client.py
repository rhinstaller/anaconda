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
import pytest
import time
import threading
from unittest.mock import Mock, patch, call
from textwrap import dedent

from pyanaconda.modules.network.nm_client import get_ports_from_connections, \
    get_dracut_arguments_from_connection, get_config_file_connection_of_device, \
    get_kickstart_network_data, NM_BRIDGE_DUMPED_SETTINGS_DEFAULTS, \
    update_connection_wired_settings_from_ksdata, get_new_nm_client, GError, \
    update_connection_ip_settings_from_ksdata
from pyanaconda.core.kickstart.commands import NetworkData
from pyanaconda.core.glib import MainContext, sync_call_glib
from pyanaconda.modules.network.constants import NM_CONNECTION_TYPE_WIFI, \
    NM_CONNECTION_TYPE_ETHERNET, NM_CONNECTION_TYPE_VLAN, NM_CONNECTION_TYPE_BOND, \
    NM_CONNECTION_TYPE_TEAM, NM_CONNECTION_TYPE_BRIDGE, NM_CONNECTION_TYPE_INFINIBAND


import gi
gi.require_version("NM", "1.0")
gi.require_version("Gio", "2.0")
from gi.repository import NM, Gio


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
    def test_get_ports_from_connections(self, get_iface_from_connection):
        nm_client = Mock()

        ENS3_UUID = "50f1ddc3-cfa5-441d-8afe-729213f5ca92"
        ENS7_UUID = "d9e90dce-93bb-4c30-be16-8f4e77744742"
        ENS8_UUID = "12740d58-c17f-4e8a-a449-2affc6298853"
        ENS11_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140a9"
        TEAM1_UUID = "39ba5d2f-90d1-4bc0-b212-57f643aa7ec1"

        cons_specs = [
            {
                "get_setting_connection.return_value.get_port_type.return_value": "",
                "get_setting_connection.return_value.get_controller.return_value": "",
                "get_id.return_value": "ens3",
                "get_uuid.return_value": ENS3_UUID,
            },
            {
                "get_setting_connection.return_value.get_port_type.return_value": "team",
                "get_setting_connection.return_value.get_controller.return_value": "team0",
                "get_id.return_value": "team_0_slave_1",
                "get_uuid.return_value": ENS7_UUID,
            },
            {
                "get_setting_connection.return_value.get_port_type.return_value": "team",
                "get_setting_connection.return_value.get_controller.return_value": "team0",
                "get_id.return_value": "team_0_slave_2",
                "get_uuid.return_value": ENS8_UUID,
            },
            {
                "get_setting_connection.return_value.get_port_type.return_value": "team",
                "get_setting_connection.return_value.get_controller.return_value": TEAM1_UUID,
                "get_id.return_value": "ens11",
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

        assert get_ports_from_connections(nm_client, "team", []) == set()
        assert get_ports_from_connections(nm_client, "bridge", ["bridge0"]) == set()
        assert get_ports_from_connections(nm_client, "team", ["team2"]) == set()
        # Matching of any specification is enough
        assert get_ports_from_connections(nm_client, "team", ["team_nonexisting", TEAM1_UUID]) == \
            set([("ens11", "ens11", ENS11_UUID)])
        assert get_ports_from_connections(nm_client, "team", ["team0"]) == \
            set([("team_0_slave_1", "ens7", ENS7_UUID), ("team_0_slave_2", "ens8", ENS8_UUID)])
        assert get_ports_from_connections(nm_client, "team", [TEAM1_UUID]) == \
            set([("ens11", "ens11", ENS11_UUID)])

    @patch("pyanaconda.modules.network.nm_client.get_connections_available_for_iface")
    @patch("pyanaconda.modules.network.nm_client.get_ports_from_connections")
    @patch("pyanaconda.modules.network.nm_client.is_s390")
    def test_get_dracut_arguments_from_connection(self, is_s390, get_ports_from_connections_mock,
                                                  get_connections_available_for_iface):
        nm_client = Mock()

        CON_UUID = "44755f4c-ee12-45b4-ba5e-e10f83de51af"

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # IPv4 target
        assert get_dracut_arguments_from_connection(nm_client, con, "ens3", "10.34.39.2",
                                                    "my.host.name") == \
            set(["ip=ens3:dhcp",
                 "ifname=ens3:11:11:11:11:11:aa"])
        # IPv6 target
        assert get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                    "my.host.name") == \
            set(["ip=ens3:auto6",
                 "ifname=ens3:11:11:11:11:11:aa"])

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
            "get_s390_subchannels.return_value": ["0.0.0900", "0.0.0901", "0.0.0902"],
            "get_property.return_value": {"layer2": "1",
                                          "portname": "FOOBAR",
                                          "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        assert get_dracut_arguments_from_connection(nm_client, con, "ens4", "10.40.49.4",
                                                    "my.host.name") == \
            set(["ip=10.34.39.44::10.34.39.2:255.255.255.0:my.host.name:ens4:none",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        assert get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                    "my.host.name") == \
            set(["ip=ens3:dhcp6"])

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        assert get_dracut_arguments_from_connection(nm_client, con, "ens3", "2001::cafe:beef",
                                                    "my.host.name") == \
            set(["ip=[2001::5/64]::[2001::1]::my.host.name:ens3:none"])

        # IPv4 config auto, team
        is_s390.return_value = False
        ip4_config_attrs = {
            "get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
        }
        ip4_config = self._get_mock_objects_from_attrs([ip4_config_attrs])[0]
        cons_attrs = [
            # team controller
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_ip4_config.return_value": ip4_config,
                "get_setting_wired.return_value": None,
                "get_connection_type.return_value": NM_CONNECTION_TYPE_TEAM,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        get_ports_from_connections_mock.return_value = set([
            ("ens7", "ens7", "6a6b4586-1e4c-451f-87fa-09b059ceba3d"),
            ("ens8", "ens8", "ac4a0747-d1ea-4119-903b-18f3adad9116"),
        ])
        # IPv4 target
        assert get_dracut_arguments_from_connection(nm_client, con, "team0", "10.34.39.2",
                                                    "my.host.name") == \
            set(["ip=team0:dhcp",
                 "team=team0:ens7,ens8"])

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
                "get_setting_vlan.return_value": setting_vlan,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # Mock parent connection
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": ["0.0.0900", "0.0.0901", "0.0.0902"],
            "get_property.return_value": {"layer2": "1",
                                          "portname": "FOOBAR",
                                          "portno": "0"},
        }
        wired_setting = self._get_mock_objects_from_attrs([wired_setting_attrs])[0]
        parent_cons_attrs = [
            {
                "get_uuid.return_value": CON_UUID,
                "get_setting_wired.return_value": wired_setting,
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        parent_cons = self._get_mock_objects_from_attrs(parent_cons_attrs)
        get_connections_available_for_iface.return_value = parent_cons
        # IPv4 target
        assert get_dracut_arguments_from_connection(nm_client, con, "ens11.111", "10.34.39.2",
                                                    "my.host.name") == \
            set(["ip=ens11.111:dhcp",
                 "vlan=ens11.111:ens11",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
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
        assert get_dracut_arguments_from_connection(nm_client, con, "ens12.111", "10.34.39.2",
                                                    "my.host.name") == \
            set(["ip=ens12.111:dhcp",
                 "vlan=ens12.111:ens12"])

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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
                "get_setting_vlan.return_value": setting_vlan,
            },
        ]
        con = self._get_mock_objects_from_attrs(cons_attrs)[0]
        # Mock parent connection
        wired_setting_attrs = {
            "get_mac_address.return_value": None,
            "get_s390_nettype.return_value": "qeth",
            "get_s390_subchannels.return_value": ["0.0.0900", "0.0.0901", "0.0.0902"],
            "get_property.return_value": {"layer2": "1",
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
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            },
        ]
        parent_cons = self._get_mock_objects_from_attrs(parent_cons_attrs)
        nm_client.get_connection_by_uuid.return_value = parent_con
        # IPv4 target
        assert get_dracut_arguments_from_connection(nm_client, con, "ens13.111", "10.34.39.2",
                                                    "my.host.name") == \
            set(["ip=ens13.111:dhcp",
                 "vlan=ens13.111:ens13",
                 "rd.znet=qeth,0.0.0900,0.0.0901,0.0.0902,layer2=1,portname=FOOBAR,portno=0"])

    @patch("pyanaconda.modules.network.nm_client.get_vlan_interface_name_from_connection")
    @patch("pyanaconda.modules.network.nm_client.is_config_file_for_system")
    @patch("pyanaconda.modules.network.nm_client.get_iface_from_hwaddr")
    @patch("pyanaconda.modules.network.nm_client.is_s390")
    def test_get_config_file_connection_of_device(self, is_s390, get_iface_from_hwaddr,
                                                  is_config_file_for_system,
                                                  get_vlan_interface_name_from_connection):
        nm_client = Mock()

        ENS3_UUID = "50f1ddc3-cfa5-441d-8afe-729213f5ca92"
        ENS3_UUID2 = "50f1ddc3-cfa5-441d-8afe-729213f5ca93"
        ENS7_UUID = "d9e90dce-93bb-4c30-be16-8f4e77744742"
        ENS7_SLAVE_UUID = "d9e90dce-93bb-4c30-be16-8f4e77744743"
        ENS8_UUID = "12740d58-c17f-4e8a-a449-2affc6298853"
        ENS9_SLAVE_UUID = "12740d58-c17f-4e8a-a449-2affc6298854"
        ENS11_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140a9"
        ENS12_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140aa"
        VLAN222_UUID = "5f825617-33cb-4230-8a74-9149d51916fb"
        VLAN223_UUID = "5f825617-33cb-4230-8a74-9149d51916fc"
        TEAM0_UUID = "b7a1ae80-3acb-4390-b4b6-0e505c897576"
        TEAM1_UUID = "b7a1ae80-3acb-4390-b4b6-0e505c897577"
        BOND0_UUID = "19b938fe-c1b3-4742-86b7-9e5339ebf7da"
        BOND1_UUID = "19b938fe-c1b3-4742-86b7-9e5339ebf7db"
        BRIDGE0_UUID = "20d375f0-53c7-44a0-ad30-304649bf2c15"
        BRIDGE1_UUID = "20d375f0-53c7-44a0-ad30-304649bf2c16"
        ENS33_UUID = "cc067154-d3b9-4208-b0c9-8262940d2380"
        ENS33_UUID2 = "cc067154-d3b9-4208-b0c9-8262940d2381"

        HWADDR_ENS3 = "52:54:00:0c:77:e4"
        HWADDR_ENS8 = "52:54:00:35:BF:0F"
        HWADDR_ENS11 = "52:54:00:0c:77:e3"

        cons_specs = [
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_interface_name.return_value": "ens3",
                "get_setting_wired.return_value.get_mac_address.return_value": None,
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_uuid.return_value": ENS3_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_setting_wired.return_value.get_mac_address.return_value": HWADDR_ENS3,
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_interface_name.return_value": None,
                "get_uuid.return_value": ENS3_UUID2,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_interface_name.return_value": "ens7",
                "get_setting_wired.return_value.get_mac_address.return_value": None,
                "get_setting_connection.return_value.get_controller.return_value": "team0",
                "get_uuid.return_value": ENS7_SLAVE_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_interface_name.return_value": "ens7",
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_setting_wired.return_value.get_mac_address.return_value": None,
                "get_uuid.return_value": ENS7_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_setting_wired.return_value.get_mac_address.return_value": HWADDR_ENS8,
                "get_interface_name.return_value": None,
                "get_uuid.return_value": ENS8_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_interface_name.return_value": "ens9",
                "get_setting_wired.return_value.get_mac_address.return_value": None,
                "get_setting_connection.return_value.get_controller.return_value": "team0",
                "get_uuid.return_value": ENS9_SLAVE_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_setting_wired.return_value.get_mac_address.return_value": HWADDR_ENS11,
                "get_interface_name.return_value": None,
                "get_uuid.return_value": ENS11_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
                "get_setting_connection.return_value.get_controller.return_value": None,
                "get_setting_wired.return_value.get_mac_address.return_value": None,
                "get_interface_name.return_value": None,
                "get_id.return_value": "ens12",
                "get_uuid.return_value": ENS12_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
                "get_interface_name.return_value": "vlan222",
                "get_uuid.return_value": VLAN222_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
                "get_interface_name.return_value": "vlan223",
                "get_uuid.return_value": VLAN223_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_BOND,
                "get_interface_name.return_value": "bond0",
                "get_uuid.return_value": BOND0_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_BOND,
                "get_interface_name.return_value": "bond1",
                "get_uuid.return_value": BOND1_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_BRIDGE,
                "get_interface_name.return_value": "bridge0",
                "get_uuid.return_value": BRIDGE0_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_BRIDGE,
                "get_interface_name.return_value": "bridge1",
                "get_uuid.return_value": BRIDGE1_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_TEAM,
                "get_interface_name.return_value": "team0",
                "get_uuid.return_value": TEAM0_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_TEAM,
                "get_interface_name.return_value": "team1",
                "get_uuid.return_value": TEAM1_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_INFINIBAND,
                "get_interface_name.return_value": "ens33",
                "get_uuid.return_value": ENS33_UUID,
            },
            {
                "get_connection_type.return_value": NM_CONNECTION_TYPE_INFINIBAND,
                "get_interface_name.return_value": "ens33",
                "get_uuid.return_value": ENS33_UUID2,
            },
        ]
        cons = self._get_mock_objects_from_attrs(cons_specs)
        nm_client.get_connections.return_value = cons

        # No config files
        is_config_file_for_system.return_value = False
        assert get_config_file_connection_of_device(nm_client, "ens3") == ""

        is_config_file_for_system.return_value = True
        is_s390.return_value = False

        # ethernet
        # interface name has precedence
        assert get_config_file_connection_of_device(nm_client, "ens3") == ENS3_UUID
        # port conections are ignored
        assert get_config_file_connection_of_device(nm_client, "ens7") == ENS7_UUID
        # port conections are ignored
        assert get_config_file_connection_of_device(nm_client, "ens9") == ""
        # config bound to hwaddr
        assert get_config_file_connection_of_device(nm_client, "ens8", device_hwaddr=HWADDR_ENS8) == \
            ENS8_UUID
        # config bound to hwaddr, no hint
        hwaddr_to_iface = {
            HWADDR_ENS3: "ens3",
            HWADDR_ENS8: "ens8",
            HWADDR_ENS11: "ens11",
        }
        get_iface_from_hwaddr.side_effect = lambda nm_client, hwaddr: hwaddr_to_iface[hwaddr]
        assert get_config_file_connection_of_device(nm_client, "ens11") == ENS11_UUID
        # config not bound
        assert get_config_file_connection_of_device(nm_client, "ens12") == ""
        # config not bound, use id (s390)
        is_s390.return_value = True
        assert get_config_file_connection_of_device(nm_client, "ens12") == ENS12_UUID
        is_s390.return_value = False

        # vlan
        get_vlan_interface_name_from_connection.return_value = "vlan222"
        assert get_config_file_connection_of_device(nm_client, "vlan222") == VLAN222_UUID
        # team
        assert get_config_file_connection_of_device(nm_client, "team0") == TEAM0_UUID
        # bond
        assert get_config_file_connection_of_device(nm_client, "bond0") == BOND0_UUID
        # bridge
        assert get_config_file_connection_of_device(nm_client, "bridge0") == BRIDGE0_UUID
        # infiniband, first wins
        assert get_config_file_connection_of_device(nm_client, "ens33") == ENS33_UUID

    @patch("pyanaconda.modules.network.nm_client.get_team_port_config_from_connection")
    @patch("pyanaconda.modules.network.nm_client.get_ports_from_connections")
    @patch("pyanaconda.modules.network.nm_client.get_iface_from_connection")
    def test_get_kicstart_network_data(self, get_iface_from_connection,
                                       get_ports_from_connections_mock,
                                       get_team_port_config_from_connection):
        """Test get_kickstart_network_data."""
        nm_client = Mock()

        ENS3_UUID = "50f1ddc3-cfa5-441d-8afe-729213f5ca92"
        ENS7_UUID = "d9e90dce-93bb-4c30-be16-8f4e77744742"
        ENS8_UUID = "12740d58-c17f-4e8a-a449-2affc6298853"
        ENS11_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140a9"
        BOND0_UUID = "1ea657e7-98a5-4b1a-bb1e-e1763f0140ab"
        BRIDGE0_UUID = "20d375f0-53c7-44a0-ad30-304649bf2c15"
        BRIDGE1_UUID = "faf37604-519a-4f70-878a-b85c66609606"
        TEAM0_UUID = "20d375f0-53c7-44a0-ad30-304649bf2c16"
        VLAN223_UUID = "5f825617-33cb-4230-8a74-9149d51916fc"

        uuid_to_iface = {
            ENS3_UUID: "ens3",
            ENS7_UUID: "ens7",
            ENS8_UUID: "ens8",
            ENS11_UUID: "ens11",
            BOND0_UUID: "bond0",
            BRIDGE0_UUID: "bridge0",
            BRIDGE1_UUID: "bridge1",
            TEAM0_UUID: "team0",
            VLAN223_UUID: "vlan223"
        }
        get_iface_from_connection.side_effect = lambda nm_client, uuid: uuid_to_iface[uuid]

        ip4_addr_1 = Mock()
        ip4_addr_1.get_address.return_value = "192.168.141.131"
        ip4_addr_1.get_prefix.return_value = 24

        ip6_addr_1 = Mock()
        ip6_addr_1.get_address.return_value = "2400:c980:0000:0002::3"
        ip6_addr_1.get_prefix.return_value = 64

        ip4_dns_list = ["192.168.154.3", "10.216.106.3"]
        ip6_dns_list = ["2001:cafe::1", "2001:cafe::2"]

        bond_options_1 = [(True, "mode", "active-backup"),
                          (True, "primary", "ens8"),
                          (False, "", "")]

        ports_of_iface = {
            "bond0": set([("bond0_slave_2", "ens8", ENS8_UUID),
                          ("bond0_slave_1", "ens7", ENS7_UUID)]),
            "team0": set([("team0_slave_1", "ens7", ENS7_UUID),
                          ("team0_slave_2", "ens8", ENS8_UUID)]),
            "bridge0": set([("bridge0_slave_1", "ens8", ENS8_UUID)]),
            "bridge1": set([("bond0", "bond0", BOND0_UUID)]),
        }
        get_ports_from_connections_mock.side_effect = \
            lambda _client, _types, ids: ports_of_iface[ids[0]]

        uuid_to_port_config = {
            ENS7_UUID: '{"prio":100,"sticky":true}',
            ENS8_UUID: '{"prio":200}',
        }
        get_team_port_config_from_connection.side_effect = \
            lambda _client, uuid: uuid_to_port_config[uuid]

        bridge_properties_1 = NM_BRIDGE_DUMPED_SETTINGS_DEFAULTS.copy()
        bridge_properties_1[NM.SETTING_BRIDGE_PRIORITY] = 32769
        bridge_properties_1[NM.SETTING_BRIDGE_MAX_AGE] = 21
        bridge_properties_1[NM.SETTING_BRIDGE_FORWARD_DELAY] = 16

        cons_to_test = [
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_controller.return_value": "team0",
            "get_interface_name.return_value": "ens3",
          }],
          ""),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_WIFI,
            "get_interface_name.return_value": "wlp61s0",
          }],
          ""),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_setting_wired.return_value.get_mtu.return_value": 1500,
            "get_uuid.return_value": ENS3_UUID,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": "RHEL",
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
         }],
          "network  --bootproto=dhcp --dhcpclass=RHEL --device=ens3 --mtu=1500 --ipv6=auto"),
         # dhcp-hostname setting the hostname is debatable and should be reviewed
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_uuid.return_value": ENS3_UUID,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": "dhcp.hostname",
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_DHCP,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
         }],
          "network  --bootproto=dhcp --device=ens3 --hostname=dhcp.hostname --ipv6=dhcp"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_autoconnect.return_value": False,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": ENS7_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_MANUAL,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 2,
            "get_setting_ip4_config.return_value.get_dns.side_effect": lambda i: ip4_dns_list[i],
            "get_setting_ip4_config.return_value.get_num_addresses.return_value": 1,
            "get_setting_ip4_config.return_value.get_gateway.return_value": "192.168.141.1",
            "get_setting_ip4_config.return_value.get_address.side_effect": lambda i: ip4_addr_1,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_DISABLED,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
         }],
          "network  --bootproto=static --device=ens7 --gateway=192.168.141.1 --ip=192.168.141.131 --nameserver=192.168.154.3,10.216.106.3 --netmask=255.255.255.0 --onboot=off --noipv6"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": ENS7_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 2,
            "get_setting_ip4_config.return_value.get_dns.side_effect": lambda i: ip4_dns_list[i],
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_addresses.return_value": 1,
            "get_setting_ip6_config.return_value.get_address.side_effect": lambda i: ip6_addr_1,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 2,
            "get_setting_ip6_config.return_value.get_gateway.return_value": "2400:c980:0000:0002::1",
            "get_setting_ip6_config.return_value.get_dns.side_effect": lambda i: ip6_dns_list[i],
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_MANUAL,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
         }],
          "network  --bootproto=dhcp --device=ens7 --nameserver=192.168.154.3,10.216.106.3,2001:cafe::1,2001:cafe::2 --ipv6=2400:c980:0000:0002::3/64 --ipv6gateway=2400:c980:0000:0002::1"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_BOND,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": BOND0_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_bond.return_value.get_num_options.return_value": 2,
            "get_setting_bond.return_value.get_option.side_effect": lambda i: bond_options_1[i],
          }],
          "network  --bootproto=dhcp --device=bond0 --ipv6=auto --bondslaves=ens7,ens8 --bondopts=mode=active-backup,primary=ens8"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_BRIDGE,
            "get_setting_connection.return_value.get_autoconnect.return_value": False,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": BRIDGE0_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_bridge.return_value.get_property.side_effect": lambda i: bridge_properties_1[i],
          }],
          "network  --bootproto=dhcp --device=bridge0 --onboot=off --ipv6=auto --bridgeslaves=ens8 --bridgeopts=priority=32769,forward-delay=16,max-age=21"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_TEAM,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": TEAM0_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_team.return_value.get_config.return_value": '{\n    "runner": {\n        "name": "activebackup",\n        "hwaddr_policy": "same_all"\n    },\n    "link_watch": {\n        "name": "ethtool"\n    }\n}',
          }],
          "network  --bootproto=dhcp --device=team0 --ipv6=auto --teamslaves=\"ens7'{\\\"prio\\\":100,\\\"sticky\\\":true}',ens8'{\\\"prio\\\":200}'\" --teamconfig=\"{\\\"runner\\\":{\\\"name\\\":\\\"activebackup\\\",\\\"hwaddr_policy\\\":\\\"same_all\\\"},\\\"link_watch\\\":{\\\"name\\\":\\\"ethtool\\\"}}\""),
         # vlan
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
            "get_setting_connection.return_value.get_interface_name.return_value": "vlan233",
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": VLAN223_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_vlan.return_value.get_id.return_value": 233,
            "get_setting_vlan.return_value.get_parent.return_value": "ens7",
          }],
          "network  --bootproto=dhcp --device=ens7 --ipv6=auto --vlanid=233 --interfacename=vlan233"),
         # vlan, parent specified by UUID
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
            "get_setting_connection.return_value.get_interface_name.return_value": "vlan233",
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": VLAN223_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_vlan.return_value.get_id.return_value": 233,
            "get_setting_vlan.return_value.get_parent.return_value": ENS7_UUID,
          }],
          "network  --bootproto=dhcp --device=ens7 --ipv6=auto --vlanid=233 --interfacename=vlan233"),
         # vlan, no interface name set
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_VLAN,
            "get_setting_connection.return_value.get_interface_name.return_value": None,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": VLAN223_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": False,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 0,
            "get_setting_ip6_config.return_value.get_dns_search.return_value": "",
            "get_setting_vlan.return_value.get_id.return_value": 233,
            "get_setting_vlan.return_value.get_parent.return_value": ENS7_UUID,
          }],
          "network  --bootproto=dhcp --device=ens7 --ipv6=auto --vlanid=233"),
         # Missing ipv4 and ipv6 config - complex virtual devices setups.
         # The resulting command may not be valid (supported by kickstart)
         # but generating should not crash.
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_BOND,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": "bridge1",
            "get_uuid.return_value": BOND0_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value": None,
            "get_setting_ip6_config.return_value": None,
            "get_setting_bond.return_value.get_num_options.return_value": 2,
            "get_setting_bond.return_value.get_option.side_effect": lambda i: bond_options_1[i],
          }],
          "network  --bootproto=dhcp --device=bond0 --bondslaves=ens7,ens8 --bondopts=mode=active-backup,primary=ens8"),
         ([{
            "get_connection_type.return_value": NM_CONNECTION_TYPE_ETHERNET,
            "get_setting_connection.return_value.get_autoconnect.return_value": True,
            "get_setting_connection.return_value.get_controller.return_value": None,
            "get_uuid.return_value": ENS3_UUID,
            "get_setting_wired.return_value.get_mtu.return_value": None,
            "get_setting_ip4_config.return_value.get_method.return_value": NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            "get_setting_ip4_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip4_config.return_value.get_dhcp_hostname.return_value": None,
            "get_setting_ip4_config.return_value.get_ignore_auto_dns.return_value": True,
            "get_setting_ip4_config.return_value.get_num_dns_searches.return_value": 1,
            "get_setting_ip4_config.return_value.get_dns_search.return_value": "fedoraproject.org",
            "get_setting_ip4_config.return_value.get_dhcp_vendor_class_identifier.return_value": None,
            "get_setting_ip6_config.return_value.get_num_dns.return_value": 0,
            "get_setting_ip6_config.return_value.get_method.return_value": NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            "get_setting_ip6_config.return_value.get_ignore_auto_dns.return_value": True,
            "get_setting_ip6_config.return_value.get_num_dns_searches.return_value": 2,
            "get_setting_ip6_config.return_value.get_dns_search.side_effect": ["example.com", "example2.com"],
          }],
          "network  --bootproto=dhcp --device=ens3 --ipv6=auto --ipv4-dns-search=fedoraproject.org --ipv6-dns-search=example.com,example2.com --ipv4-ignore-auto-dns --ipv6-ignore-auto-dns"),
        ]

        for cons_specs, expected_ks in cons_to_test:
            connection = self._get_mock_objects_from_attrs(cons_specs)[0]
            generated_ks = get_kickstart_network_data(connection, nm_client, NetworkData) or ""
            if expected_ks:
                expected_ks = dedent(expected_ks).strip()
            if generated_ks:
                generated_ks = dedent(str(generated_ks)).strip()
            assert generated_ks == expected_ks

    def test_update_connection_wired_settings_from_ksdata(self):
        """Test update_connection_wired_settings_from_ksdata."""
        network_data = Mock()
        connection = Mock()
        wired_setting = Mock()

        connection.get_setting_wired.return_value = wired_setting

        # --mtu default value
        network_data.mtu = ""
        update_connection_wired_settings_from_ksdata(connection, network_data)
        connection.get_setting_wired.assert_not_called()

        # Invalid value
        # --mtu=non-int
        network_data.mtu = "non-int"
        connection.reset_mock()
        update_connection_wired_settings_from_ksdata(connection, network_data)
        connection.get_setting_wired.assert_not_called()

        # Valid value
        # --mtu=9000
        # The connection already has wired setting
        connection.reset_mock()
        network_data.mtu = "9000"
        update_connection_wired_settings_from_ksdata(connection, network_data)
        connection.get_setting_wired.assert_called_once()

        # Valid value
        # --mtu=9000
        # The connection does not have wired setting yet
        connection.get_setting_wired.return_value = None
        connection.reset_mock()
        update_connection_wired_settings_from_ksdata(connection, network_data)
        connection.add_setting.assert_called_once()

    @patch("pyanaconda.modules.network.nm_client.NM")
    @patch("pyanaconda.modules.network.nm_client.SystemBus")
    def test_get_new_nm_client(self, system_bus, nm):
        """Test get_new_nm_client."""
        nm_client = Mock()

        system_bus.check_connection.return_value = False

        assert get_new_nm_client() is None

        system_bus.check_connection.return_value = True

        nm.Client.new.return_value = nm_client
        nm_client.get_nm_running.return_value = False
        assert get_new_nm_client() is None

        nm_client.get_nm_running.return_value = True
        assert get_new_nm_client() is not None

        nm.Client.new.side_effect = GError
        assert get_new_nm_client() is None

    def test_sync_call_glib(self):

        mainctx = MainContext.new()
        mainctx.push_thread_default()

        timeout = 1
        attributes = "*"
        flags = Gio.FileQueryInfoFlags.NONE
        io_priority = 1
        filename = "usr"
        filepath = "/" + filename

        # Test successful run
        file = Gio.file_new_for_path(filepath)
        result = sync_call_glib(
            mainctx,
            file.query_info_async,
            file.query_info_finish,
            timeout,
            attributes,
            flags,
            io_priority
        )
        assert result.succeeded is True
        assert result.failed is False
        assert result.error_message == ""
        assert result.received_data.get_name() == filename
        assert result.timeout is False

        # Test run with error
        filepath = "/nowaythiscanbeonyourfilesystem"
        file = Gio.file_new_for_path(filepath)
        result = sync_call_glib(
            mainctx,
            file.query_info_async,
            file.query_info_finish,
            timeout,
            attributes,
            flags,
            io_priority
        )
        assert result.succeeded is False
        assert result.failed is True
        assert result.error_message != ""
        assert result.received_data is None
        assert result.timeout is False

        # Test timeout
        delay = timeout + 1
        filepath = "/" + filename
        file = Gio.file_new_for_path(filepath)

        def _file_query_info_async_with_delay(
            delay,
            *args,
            cancellable,
            callback
        ):
            time.sleep(delay)
            return Gio.File.query_info_async(
                *args,
                cancellable,
                callback
            )

        _file_query_info_async_with_delay.get_symbol = lambda: "_file_query_info_async_with_delay"

        result = sync_call_glib(
            mainctx,
            _file_query_info_async_with_delay,
            file.query_info_finish,
            timeout,
            delay,
            file,
            attributes,
            flags,
            io_priority
        )

        assert result.succeeded is False
        assert result.error_message == "g-io-error-quark: Operation was cancelled (19)"
        assert result.received_data is None
        assert result.timeout is True

        mainctx.pop_thread_default()

    # Don't ignore AssertionError from rised from the Thread
    @pytest.mark.filterwarnings("error")
    def test_sync_call_glib_in_thread(self):
        thread = threading.Thread(target = self.test_sync_call_glib)
        thread.start()
        thread.join()

    @patch("pyanaconda.modules.network.nm_client.NM.SettingIP4Config.new")
    @patch("pyanaconda.modules.network.nm_client.NM.SettingIP6Config.new")
    def _dns_ksdata_to_ip_sets(self, ipv4_search, ipv6_search, ipv4_ignoreauto, ipv6_ignoreauto,
                               new6, new4):
        connection = Mock()
        ksdata = NetworkData(
            ipv4_dns_search=ipv4_search,
            ipv6_dns_search=ipv6_search,
            ipv4_ignore_auto_dns=ipv4_ignoreauto,
            ipv6_ignore_auto_dns=ipv6_ignoreauto
        )

        update_connection_ip_settings_from_ksdata(connection, ksdata)
        new4.assert_called_once_with()
        new6.assert_called_once_with()
        connection.remove_setting.assert_called()
        connection.add_setting.assert_called()

        s_ipv4 = connection.add_setting.mock_calls[0].args[0]
        s_ipv6 = connection.add_setting.mock_calls[1].args[0]
        assert new4.return_value == s_ipv4
        assert new6.return_value == s_ipv6

        # these are set only if True, so skip comparing False with the implicitly present Mock
        if ipv4_ignoreauto is True:
            assert s_ipv4.props.ignore_auto_dns == ipv4_ignoreauto
        if ipv6_ignoreauto is True:
            assert s_ipv6.props.ignore_auto_dns == ipv6_ignoreauto

        return s_ipv4, s_ipv6

    def test_dns_update_connection_ip_settings_from_ksdata(self):
        """Test DNS handling in update_connection_ip_settings_from_ksdata()"""
        # pylint: disable=no-value-for-parameter
        # first search domains
        sv4, sv6 = self._dns_ksdata_to_ip_sets("fedoraproject.org,getfedora.org", "redhat.com", False, False)
        sv4.add_dns_search.assert_has_calls([
            call("fedoraproject.org"),
            call("getfedora.org")
        ])
        sv6.add_dns_search.assert_called_once_with("redhat.com")

        # then check permutations of the ignore_auto_dns props + no search domains
        sv4, sv6 = self._dns_ksdata_to_ip_sets(None, None, False, False)
        sv4.add_dns_search.assert_not_called()
        sv6.add_dns_search.assert_not_called()

        sv4, sv6 = self._dns_ksdata_to_ip_sets(None, None, True, True)
        sv4.add_dns_search.assert_not_called()
        sv6.add_dns_search.assert_not_called()

        sv4, sv6 = self._dns_ksdata_to_ip_sets(None, None, True, False)
        sv4.add_dns_search.assert_not_called()
        sv6.add_dns_search.assert_not_called()

        sv4, sv6 = self._dns_ksdata_to_ip_sets(None, None, False, False)
        sv4.add_dns_search.assert_not_called()
        sv6.add_dns_search.assert_not_called()
