#
# Copyright (C) 2020  Red Hat, Inc.
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
import unittest
from unittest.mock import patch

from pyanaconda.core.constants import SOURCE_TYPE_NFS
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_NFS
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.nfs.nfs import NFSSourceModule
from pyanaconda.modules.payloads.source.nfs.nfs_interface import NFSSourceInterface
from pyanaconda.modules.payloads.source.nfs.initialization import SetUpNFSSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.payload.utils import PayloadSetupError

from tests.nosetests.pyanaconda_tests import check_dbus_property, PropertiesChangedCallback


nfs_address = "example.com:/some/path"
nfs_url = "nfs:" + nfs_address
mount_location = "/mnt/put-nfs-here"


class NFSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()
        self.interface = NFSSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def type_test(self):
        """Test NFS source has a correct type specified."""
        self.assertEqual(SOURCE_TYPE_NFS, self.interface.Type)

    def description_test(self):
        """Test NFS source description."""
        self.interface.SetURL("nfs:server:/path")
        self.assertEqual("NFS server nfs:server:/path", self.interface.Description)

    def url_empty_properties_test(self):
        """Test NFS source URL property when not set."""
        self.assertEqual(self.interface.URL, "")

    def url_properties_test(self):
        """Test NFS source URL property is correctly set."""
        check_dbus_property(
            self,
            PAYLOAD_SOURCE_NFS,
            self.interface,
            "URL",
            nfs_url
        )


class NFSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()

    def type_test(self):
        """Test NFS source module has a correct type."""
        self.assertEqual(SourceType.NFS, self.module.type)

    def network_required_test(self):
        """Test the property network_required."""
        self.assertEqual(self.module.network_required, True)

    @patch("os.path.ismount")
    def get_state_test(self, ismount_mock):
        """Test NFS source state."""
        ismount_mock.return_value = False
        self.assertEqual(SourceState.UNREADY, self.module.get_state())

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        self.assertEqual(SourceState.READY, self.module.get_state())

        ismount_mock.assert_called_once_with(self.module.mount_point)

    def set_up_with_tasks_test(self):
        """Test NFS Source set up call."""
        task_classes = [
            SetUpNFSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def tear_down_with_tasks_test(self):
        """Test NFS Source ready state for tear down."""
        task_classes = [
            TearDownMountTask,
            TearDownMountTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.tear_down_with_tasks()

        # check the number of tasks
        task_number = len(task_classes)
        self.assertEqual(task_number, len(tasks))

        for i in range(task_number):
            self.assertIsInstance(tasks[i], task_classes[i])

    def url_property_test(self):
        """Test NFS source URL property is correctly set."""
        self.module.set_url(nfs_url)
        self.assertEqual(nfs_url, self.module.url)

    def repr_test(self):
        self.module.set_url(nfs_url)
        self.assertEqual(
            repr(self.module),
            "Source(type='NFS', url='nfs:example.com:/some/path')"
        )


class NFSSourceSetupTaskTestCase(unittest.TestCase):

    def setup_install_source_task_name_test(self):
        """Test NFS Source setup installation source task name."""
        task = SetUpNFSSourceTask(mount_location, nfs_url)
        self.assertEqual(task.name, "Set up NFS installation source")

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def setup_install_source_task_success_test(self, mount_mock):
        """Test NFS source setup success"""
        SetUpNFSSourceTask(mount_location, nfs_url).run()
        mount_mock.assert_called_once_with(nfs_address, mount_location, fstype="nfs",
                                           options="nolock")

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def setup_install_source_task_options_nolock_test(self, mount_mock):
        """Test NFS source setup adding nolock to options """
        SetUpNFSSourceTask(mount_location, "nfs:some-option:" + nfs_address).run()
        mount_mock.assert_called_with(nfs_address, mount_location, fstype="nfs",
                                      options="some-option,nolock")

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def setup_install_source_task_success_options_test(self, mount_mock):
        """Test NFS source setup handling nolock in options"""
        SetUpNFSSourceTask(mount_location, "nfs:some-option,nolock:" + nfs_address).run()
        mount_mock.assert_called_with(nfs_address, mount_location, fstype="nfs",
                                      options="some-option,nolock")

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount",
           side_effect=PayloadSetupError("Testing..."))
    def setup_install_source_task_failure_test(self, mount_mock):
        """Test NFS source setup failure"""
        task = SetUpNFSSourceTask(mount_location, nfs_url)

        with self.assertRaises(PayloadSetupError):
            task.run()

        mount_mock.assert_called_once_with(nfs_address, mount_location, fstype="nfs",
                                           options="nolock")
