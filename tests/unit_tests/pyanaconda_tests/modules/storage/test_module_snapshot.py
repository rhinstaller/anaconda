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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from unittest.mock import Mock, patch

import pytest
from blivet.errors import StorageError
from pykickstart.constants import SNAPSHOT_WHEN_POST_INSTALL, SNAPSHOT_WHEN_PRE_INSTALL

from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.snapshot import SnapshotModule
from pyanaconda.modules.storage.snapshot.create import SnapshotCreateTask
from pyanaconda.modules.storage.snapshot.device import get_snapshot_device
from pyanaconda.modules.storage.snapshot.snapshot_interface import SnapshotInterface
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation,
    patch_dbus_publish_object,
)


class SnapshotInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the Snapshot module."""

    def setUp(self):
        """Set up the module."""
        self.module = SnapshotModule()
        self.interface = SnapshotInterface(self.module)

    def test_is_requested(self):
        """Test IsRequested."""
        assert self.interface.IsRequested(SNAPSHOT_WHEN_PRE_INSTALL) is False
        assert self.interface.IsRequested(SNAPSHOT_WHEN_POST_INSTALL) is False

        self.module._requests = [Mock(when=SNAPSHOT_WHEN_PRE_INSTALL)]
        assert self.interface.IsRequested(SNAPSHOT_WHEN_PRE_INSTALL) is True
        assert self.interface.IsRequested(SNAPSHOT_WHEN_POST_INSTALL) is False

        self.module._requests = [Mock(when=SNAPSHOT_WHEN_POST_INSTALL)]
        assert self.interface.IsRequested(SNAPSHOT_WHEN_PRE_INSTALL) is False
        assert self.interface.IsRequested(SNAPSHOT_WHEN_POST_INSTALL) is True

        self.module._requests = [Mock(when=SNAPSHOT_WHEN_PRE_INSTALL),
                                 Mock(when=SNAPSHOT_WHEN_POST_INSTALL)]
        assert self.interface.IsRequested(SNAPSHOT_WHEN_PRE_INSTALL) is True
        assert self.interface.IsRequested(SNAPSHOT_WHEN_POST_INSTALL) is True

    @patch_dbus_publish_object
    def test_create_with_task(self, publisher):
        """Test CreateWithTask."""
        with pytest.raises(UnavailableStorageError):
            self.interface.CreateWithTask(SNAPSHOT_WHEN_PRE_INSTALL)

        self.module.on_storage_changed(Mock())
        task_path = self.interface.CreateWithTask(SNAPSHOT_WHEN_PRE_INSTALL)

        obj = check_task_creation(task_path, publisher, SnapshotCreateTask)

        assert obj.implementation._storage == self.module.storage
        assert obj.implementation._requests == []
        assert obj.implementation._when == SNAPSHOT_WHEN_PRE_INSTALL

    @patch('pyanaconda.modules.storage.snapshot.snapshot.get_snapshot_device')
    def test_verify_requests(self, device_getter):
        """Test the verify_requests method."""
        report_error = Mock()
        report_warning = Mock()
        self.module._requests = [Mock(when=SNAPSHOT_WHEN_POST_INSTALL)]

        # Test passing check.
        self.module.verify_requests(Mock(), Mock(), report_error, report_warning)
        report_error.assert_not_called()
        report_warning.assert_not_called()

        # Test failing check.
        device_getter.side_effect = StorageError("Fake error")
        self.module.verify_requests(Mock(), Mock(), report_error, report_warning)
        report_error.assert_called_once_with("Fake error")
        report_warning.assert_not_called()


class SnapshotTasksTestCase(unittest.TestCase):
    """Test snapshot tasks."""

    def test_get_snapshot_device_fail(self):
        """Test the snapshot device."""
        with pytest.raises(StorageError):
            get_snapshot_device(Mock(name="post-snapshot", origin="fedora/root"), Mock())

    @patch('pyanaconda.modules.storage.snapshot.device.LVMLogicalVolumeDevice')
    def test_get_snapshot_device(self, device_class):
        """Test the snapshot device."""
        device = Mock()
        device_class.return_value = device

        devicetree = Mock()
        devicetree.get_device_by_name.side_effect = [Mock(), None]

        request = Mock(name="post-snapshot", origin="fedora/root")
        assert get_snapshot_device(request, devicetree) == device

    @patch('pyanaconda.modules.storage.snapshot.create.get_snapshot_device')
    def test_creation(self, device_getter):
        """Test the creation task."""
        SnapshotCreateTask(Mock(), [], SNAPSHOT_WHEN_PRE_INSTALL).run()
        device_getter.assert_not_called()

        SnapshotCreateTask(Mock(), [Mock()], SNAPSHOT_WHEN_POST_INSTALL).run()
        device_getter.assert_called_once()
