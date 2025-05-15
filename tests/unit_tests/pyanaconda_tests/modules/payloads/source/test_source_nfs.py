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
from unittest.mock import Mock, patch

import pytest

from pyanaconda.core.constants import SOURCE_TYPE_NFS
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_NFS
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.nfs.initialization import SetUpNFSSourceTask
from pyanaconda.modules.payloads.source.nfs.nfs import NFSSourceModule
from pyanaconda.modules.payloads.source.nfs.nfs_interface import NFSSourceInterface
from pyanaconda.payload.utils import PayloadSetupError
from tests.unit_tests.pyanaconda_tests import (
    PropertiesChangedCallback,
    check_dbus_property,
)

NFS_ADDRESS = "example.com:/some/path"
NFS_URL = "nfs:" + NFS_ADDRESS
DEVICE_MOUNT_LOCATION = "/mnt/put-nfs-here"
ISO_MOUNT_LOCATION = "/mnt/put-nfs-iso-here"


def _create_setup_task(url=NFS_URL):
    return SetUpNFSSourceTask(
        DEVICE_MOUNT_LOCATION,
        ISO_MOUNT_LOCATION,
        url
    )


class NFSSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()
        self.interface = NFSSourceInterface(self.module)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def test_type(self):
        """Test NFS source has a correct type specified."""
        assert SOURCE_TYPE_NFS == self.interface.Type

    def test_description(self):
        """Test NFS source description."""
        self.interface.SetURL("nfs:server:/path")
        assert "NFS server nfs:server:/path" == self.interface.Description

    def test_url_empty_properties(self):
        """Test NFS source URL property when not set."""
        assert self.interface.URL == ""

    def test_url_properties(self):
        """Test NFS source URL property is correctly set."""
        check_dbus_property(
            PAYLOAD_SOURCE_NFS,
            self.interface,
            "URL",
            NFS_URL
        )


class NFSSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = NFSSourceModule()

    def test_type(self):
        """Test NFS source module has a correct type."""
        assert SourceType.NFS == self.module.type

    def test_network_required(self):
        """Test the property network_required."""
        assert self.module.network_required is True

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 0

    @patch("os.path.ismount")
    def test_get_state(self, ismount_mock):
        """Test NFS source state."""
        ismount_mock.return_value = False
        assert SourceState.UNREADY == self.module.get_state()

        ismount_mock.reset_mock()
        ismount_mock.return_value = True

        task = self.module.set_up_with_tasks()[0]
        task.get_result = Mock(return_value="/my/path")
        task.succeeded_signal.emit()
        assert SourceState.READY == self.module.get_state()

        ismount_mock.assert_called_once_with(self.module._device_mount)

    def test_set_up_with_tasks(self):
        """Test NFS Source set up call."""
        task_classes = [
            SetUpNFSSourceTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.set_up_with_tasks()

        # Check the number of the tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_tear_down_with_tasks(self):
        """Test NFS Source ready state for tear down."""
        task_classes = [
            TearDownMountTask,
            TearDownMountTask
        ]

        # task will not be public so it won't be published
        tasks = self.module.tear_down_with_tasks()

        # check the number of tasks
        task_number = len(task_classes)
        assert task_number == len(tasks)

        for i in range(task_number):
            assert isinstance(tasks[i], task_classes[i])

    def test_url_property(self):
        """Test NFS source URL property is correctly set."""
        self.module.set_url(NFS_URL)
        assert NFS_URL == self.module.url

    def test_repr(self):
        self.module.set_url(NFS_URL)
        assert repr(self.module) == "Source(type='NFS', url='nfs:example.com:/some/path')"


class NFSSourceSetupTaskTestCase(unittest.TestCase):

    def test_setup_install_source_task_name(self):
        """Test NFS Source setup installation source task name."""
        task = SetUpNFSSourceTask(DEVICE_MOUNT_LOCATION, ISO_MOUNT_LOCATION, NFS_URL)
        assert task.name == "Set up NFS installation source"

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="trojan.iso")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_iso(self,
                              mount_mock,
                              find_and_mount_iso_image_mock):
        """Test NFS source setup find ISO success"""
        task = _create_setup_task()
        result = task.run()

        mount_mock.assert_called_once_with(NFS_ADDRESS,
                                           DEVICE_MOUNT_LOCATION,
                                           fstype="nfs",
                                           options="nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION,
                                                              ISO_MOUNT_LOCATION)

        assert result == ISO_MOUNT_LOCATION

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="trojan.iso")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_path_with_iso(self,
                                        mount_mock,
                                        find_and_mount_iso_image_mock):
        """Test NFS source setup when url has ISO in a path success"""
        task = _create_setup_task("nfs:secret.com:/path/to/super.iso")
        result = task.run()

        mount_mock.assert_called_once_with("secret.com:/path/to",
                                           DEVICE_MOUNT_LOCATION,
                                           fstype="nfs",
                                           options="nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION + "/super.iso",
                                                              ISO_MOUNT_LOCATION)

        assert result == ISO_MOUNT_LOCATION

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.verify_valid_repository",
           return_value=True)
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_success_find_dir(self,
                              mount_mock,
                              find_and_mount_iso_image_mock,
                              verify_valid_repository_mock):
        """Test NFS source setup find installation tree success"""
        task = _create_setup_task()
        result = task.run()

        mount_mock.assert_called_once_with(NFS_ADDRESS,
                                           DEVICE_MOUNT_LOCATION,
                                           fstype="nfs",
                                           options="nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION,
                                                              ISO_MOUNT_LOCATION)

        verify_valid_repository_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION)

        assert result == DEVICE_MOUNT_LOCATION

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="trojan.iso")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_setup_install_source_task_options_nolock(self,
                                                      mount_mock,
                                                      find_and_mount_iso_image_mock):
        """Test NFS source setup adding nolock to options"""
        task = SetUpNFSSourceTask(DEVICE_MOUNT_LOCATION,
                                  ISO_MOUNT_LOCATION,
                                  "nfs:some-option:" + NFS_ADDRESS)
        task.run()
        mount_mock.assert_called_with(NFS_ADDRESS, DEVICE_MOUNT_LOCATION, fstype="nfs",
                                      options="some-option,nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION,
                                                              ISO_MOUNT_LOCATION)

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="trojan.iso")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_setup_install_source_task_success_options(self,
                                                       mount_mock,
                                                       find_and_mount_iso_image_mock):
        """Test NFS source setup handling nolock in options"""
        task = SetUpNFSSourceTask(DEVICE_MOUNT_LOCATION,
                                  ISO_MOUNT_LOCATION,
                                  "nfs:some-option,nolock:" + NFS_ADDRESS)
        task.run()
        mount_mock.assert_called_with(NFS_ADDRESS, DEVICE_MOUNT_LOCATION, fstype="nfs",
                                      options="some-option,nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION,
                                                              ISO_MOUNT_LOCATION)

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount",
           side_effect=PayloadSetupError("Testing..."))
    def test_setup_install_source_task_mount_failure(self, mount_mock):
        """Test NFS source setup failure"""
        task = SetUpNFSSourceTask(DEVICE_MOUNT_LOCATION, ISO_MOUNT_LOCATION, NFS_URL)

        with pytest.raises(SourceSetupError):
            task.run()

        mount_mock.assert_called_once_with(NFS_ADDRESS, DEVICE_MOUNT_LOCATION, fstype="nfs",
                                           options="nolock")

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.unmount")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.verify_valid_repository",
           return_value=False)
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.find_and_mount_iso_image",
           return_value="")
    @patch("pyanaconda.modules.payloads.source.nfs.initialization.mount")
    def test_setup_install_source_task_find_anything_failure(self,
                                                             mount_mock,
                                                             find_and_mount_iso_image_mock,
                                                             verify_valid_repository_mock,
                                                             unmount_mock):
        """Test NFS can't find anything to install from"""
        task = SetUpNFSSourceTask(DEVICE_MOUNT_LOCATION, ISO_MOUNT_LOCATION, NFS_URL)

        with pytest.raises(SourceSetupError):
            task.run()

        mount_mock.assert_called_once_with(NFS_ADDRESS, DEVICE_MOUNT_LOCATION, fstype="nfs",
                                           options="nolock")

        find_and_mount_iso_image_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION,
                                                              ISO_MOUNT_LOCATION)

        verify_valid_repository_mock.assert_called_once_with(DEVICE_MOUNT_LOCATION)

        unmount_mock.assert_called_once_with(
            DEVICE_MOUNT_LOCATION
        )

    @patch("pyanaconda.modules.payloads.source.nfs.initialization.os.path.ismount",
           return_value=True)
    def test_failure_mount_already_used(self, ismount_mock):
        """NFS source setup failure to mount partition device."""
        task = _create_setup_task()
        with pytest.raises(SourceSetupError) as cm:
            task.run()

        ismount_mock.assert_called_once()  # must die on first check
        assert str(cm.value).startswith(
            "The mount point"
        )


class NFSSourceTearDownTestCase(unittest.TestCase):

    def setUp(self):
        self.source_module = NFSSourceModule()

    def test_tear_down_task_order(self):
        """NFS source tear down task order."""
        tasks = self.source_module.tear_down_with_tasks()
        assert len(tasks) == 2
        assert isinstance(tasks[0], TearDownMountTask)
        assert isinstance(tasks[1], TearDownMountTask)
        name_suffixes = ["-iso", "-device"]
        for task, fragment in zip(tasks, name_suffixes):
            assert task._target_mount.endswith(fragment)
