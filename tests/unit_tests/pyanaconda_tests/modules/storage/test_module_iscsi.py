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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from unittest.mock import Mock, patch

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.constants.objects import ISCSI
from pyanaconda.modules.common.structures.iscsi import Portal, Credentials, Node
from pyanaconda.modules.storage.constants import IscsiInterfacesMode
from pyanaconda.modules.storage.iscsi import ISCSIModule
from pyanaconda.modules.storage.iscsi.discover import ISCSIDiscoverTask, ISCSILoginTask
from pyanaconda.modules.storage.iscsi.iscsi_interface import ISCSIInterface, \
    ISCSIDiscoverTaskInterface
from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation, \
    check_dbus_property


class ISCSIInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the iSCSI module."""

    def setUp(self):
        """Set up the module."""
        self.iscsi_module = ISCSIModule()
        self.iscsi_interface = ISCSIInterface(self.iscsi_module)

        self._portal = Portal()
        self._portal.ip_address = "10.43.136.67"
        self._portal.port = "3260"

        self._credentials = Credentials()
        self._credentials.username = "mersault"
        self._credentials.password = "nothing"
        self._credentials.reverse_username = "tluasrem"
        self._credentials.reverse_password = "thing"

        self._node = Node()
        self._node.name = "iqn.2014-08.com.example:t1"
        self._node.address = "10.43.136.67"
        self._node.port = "3260"
        self._node.iface = "iface0"
        self._node.net_ifacename = "ens3"

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            ISCSI,
            self.iscsi_interface,
            *args, **kwargs
        )

    @patch("pyanaconda.modules.storage.iscsi.iscsi.iscsi", available=True)
    def test_is_supported(self, iscsi):
        assert self.iscsi_interface.IsSupported() is True

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_initator_property_unset(self, iscsi):
        """Test Initiator property as unset."""
        iscsi.initiator_set = False
        self._check_dbus_property(
            "Initiator",
            "iqn.1994-05.com.redhat:blabla"
        )

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_initator_property_set(self, iscsi):
        """Test Initiator property as set."""
        original_initiator = "iqn.1994-05.com.redhat:blabla"
        new_initiator = "iqn.1995-06.com.redhat:qweqwe"

        iscsi.initiator_set = True
        iscsi.initiator = original_initiator

        self.iscsi_interface.Initiator = new_initiator
        assert self.iscsi_interface.Initiator == original_initiator

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_can_set_initiator(self, iscsi):
        """Test CanSetInitiator method."""
        assert isinstance(self.iscsi_interface.CanSetInitiator(), bool)

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_get_interface_mode(self, iscsi):
        """Test GetInterfaceMode method."""
        blivet_mode_values = ["none", "default", "bind"]
        for blivet_mode in blivet_mode_values + ["unexpected_value"]:
            iscsi.mode = blivet_mode
            _mode = IscsiInterfacesMode(self.iscsi_interface.GetInterfaceMode())

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_is_node_from_ibft(self, iscsi):
        """Test IsNodeFromIbft method."""
        iscsi.ibft_nodes = []
        result = self.iscsi_interface.IsNodeFromIbft(
            Node.to_structure(self._node)
        )
        assert not result

        blivet_node = Mock()
        blivet_node.name = self._node.name
        blivet_node.address = self._node.address
        blivet_node.port = int(self._node.port)
        blivet_node.iface = self._node.iface
        iscsi.ibft_nodes = [blivet_node]
        result = self.iscsi_interface.IsNodeFromIbft(
            Node.to_structure(self._node)
        )
        assert result

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_get_interface(self, iscsi):
        """Test GetInterface method."""
        iscsi.ifaces = {
            "iface0" : "ens3",
            "iface1" : "ens7",
        }
        assert self.iscsi_interface.GetInterface("iface0") == "ens3"
        assert self.iscsi_interface.GetInterface("nonexisting") == ""

    @patch_dbus_publish_object
    def test_discover_with_task(self, publisher):
        """Test the discover task."""
        interfaces_mode = "default"
        task_path = self.iscsi_interface.DiscoverWithTask(
            Portal.to_structure(self._portal),
            Credentials.to_structure(self._credentials),
            interfaces_mode
        )

        obj = check_task_creation(task_path, publisher, ISCSIDiscoverTask)

        assert isinstance(obj, ISCSIDiscoverTaskInterface)

        assert obj.implementation._portal == self._portal
        assert obj.implementation._credentials == self._credentials
        assert obj.implementation._interfaces_mode == IscsiInterfacesMode.DEFAULT

    @patch_dbus_publish_object
    def test_login_with_task(self, publisher):
        """Test the login task."""
        task_path = self.iscsi_interface.LoginWithTask(
            Portal.to_structure(self._portal),
            Credentials.to_structure(self._credentials),
            Node.to_structure(self._node),
        )

        obj = check_task_creation(task_path, publisher, ISCSILoginTask)

        assert obj.implementation._portal == self._portal
        assert obj.implementation._credentials == self._credentials
        assert obj.implementation._node == self._node

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_write_configuration(self, iscsi):
        """Test WriteConfiguration."""
        self.iscsi_interface.WriteConfiguration()
        iscsi.write.assert_called_once_with(conf.target.system_root, None)

    @patch('pyanaconda.modules.storage.iscsi.iscsi.iscsi')
    def test_get_dracut_arguments(self, iscsi):
        """Test the get_dracut_arguments function."""
        blivet_node = Mock()
        blivet_node.name = self._node.name
        blivet_node.address = self._node.address
        blivet_node.port = int(self._node.port)
        blivet_node.iface = self._node.iface

        # The node is iBFT node
        iscsi.ibft_nodes = [blivet_node]
        assert self.iscsi_interface.GetDracutArguments(Node.to_structure(self._node)) == \
            ["rd.iscsi.firmware"]

        # The node is not found
        iscsi.ibft_nodes = []
        iscsi.get_node.return_value = None
        assert self.iscsi_interface.GetDracutArguments(Node.to_structure(self._node)) == \
            []

        iscsi.ifaces = {
            "iface0": "ens3",
            "iface1": "ens7",
        }

        # The node is active
        iscsi.get_node.return_value = blivet_node
        blivet_node.username = ""
        blivet_node.r_username = ""
        blivet_node.password = ""
        blivet_node.r_password = ""
        iscsi.initiator = "iqn.1994-05.com.redhat:blablabla"
        assert self.iscsi_interface.GetDracutArguments(Node.to_structure(self._node)) == \
            ["netroot=iscsi:@10.43.136.67::3260:iface0:ens3::iqn.2014-08.com.example:t1",
             "rd.iscsi.initiator=iqn.1994-05.com.redhat:blablabla"]

        # The node is active, with default interface
        iscsi.get_node.return_value = blivet_node
        blivet_node.iface = "default"
        iscsi.initiator = "iqn.1994-05.com.redhat:blablabla"
        assert self.iscsi_interface.GetDracutArguments(Node.to_structure(self._node)) == \
            ["netroot=iscsi:@10.43.136.67::3260::iqn.2014-08.com.example:t1",
             "rd.iscsi.initiator=iqn.1994-05.com.redhat:blablabla"]

        # The node is active, with offload interface, and reverse chap
        iscsi.get_node.return_value = blivet_node
        blivet_node.username = "uname"
        blivet_node.r_username = "r_uname"
        blivet_node.password = "passwd"
        blivet_node.r_password = "r_passwd"
        blivet_node.iface = "qedi.a6:26:77:80:00:63"
        iscsi.initiator = "iqn.1994-05.com.redhat:blablabla"
        assert self.iscsi_interface.GetDracutArguments(Node.to_structure(self._node)) == \
            ["netroot=iscsi:uname:passwd:r_uname:r_passwd@10.43.136.67::3260:qedi.a6:26:77:80:00:63:qedi.a6:26:77:80:00:63::iqn.2014-08.com.example:t1",
             "rd.iscsi.initiator=iqn.1994-05.com.redhat:blablabla"]
