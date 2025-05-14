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
import os
import pickle
import sys
import unittest
from unittest.mock import patch

import pytest

from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.partitioning.blivet.blivet_interface import (
    BlivetPartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.blivet.blivet_module import (
    BlivetPartitioningModule,
)
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import (
    InteractivePartitioningTask,
)
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation,
    patch_dbus_publish_object,
)

# blivet-gui is supported on Fedora, but not ELN/CentOS/RHEL
HAVE_BLIVET_GUI = os.path.exists("/usr/bin/blivet-gui")


class BlivetPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the Blivet partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = BlivetPartitioningModule()
        self.interface = BlivetPartitioningInterface(self.module)

    @patch.dict('sys.modules')
    def test_unsupported_partitioning(self):
        """Test the UnsupportedPartitioningError."""
        # Forget imported modules from pyanaconda and blivetgui.
        for name in list(sys.modules):
            if name.startswith('pyanaconda') or name.startswith('blivetgui'):
                sys.modules.pop(name)

        # Disable the blivetgui package.
        sys.modules['blivetgui'] = None

        # Import the StorageModule again.
        from pyanaconda.modules.storage.storage import StorageService

        # We should be able to create the Storage module
        storage_module = StorageService()
        assert storage_module.storage is not None

        # We should be able to create the Blivet module.
        from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
        blivet_module = storage_module.create_partitioning(PartitioningMethod.BLIVET)
        assert blivet_module.storage is not None

        # Import the exception again.
        from pyanaconda.modules.common.errors.storage import (
            UnsupportedPartitioningError,
        )

        # Handle the missing support.
        with pytest.raises(UnsupportedPartitioningError):
            assert not blivet_module.storage_handler

        with pytest.raises(UnsupportedPartitioningError):
            assert not blivet_module.request_handler

        with pytest.raises(UnsupportedPartitioningError):
            request = pickle.dumps(("call", "get_disks", []))
            blivet_module.send_request(request)

    @unittest.skipUnless(HAVE_BLIVET_GUI, "blivet-gui not installed")
    def test_storage_handler(self):
        """Test the storage_handler property."""
        self.module.on_storage_changed(create_storage())
        assert self.module.storage_handler is not None
        assert self.module.storage == self.module.storage_handler.storage

    @unittest.skipUnless(HAVE_BLIVET_GUI, "blivet-gui not installed")
    def test_request_handler(self):
        """Test the request_handler property."""
        self.module.on_storage_changed(create_storage())
        assert self.module.request_handler is not None
        assert self.module.storage_handler == self.module.request_handler.blivet_utils

    @unittest.skipUnless(HAVE_BLIVET_GUI, "blivet-gui not installed")
    def test_send_request(self):
        """Test SendRequest."""
        self.module.on_storage_changed(create_storage())
        request = pickle.dumps(("call", "get_disks", []))

        answer = self.interface.SendRequest(request)
        answer = pickle.loads(answer)

        from blivetgui.communication.proxy_utils import (
            ProxyID,  # pylint: disable=import-error
        )
        assert isinstance(answer, ProxyID)
        assert answer.id == 0

    @patch_dbus_publish_object
    def test_configure_with_task(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(create_storage())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(task_path, publisher, InteractivePartitioningTask)

        assert obj.implementation._storage == self.module.storage
