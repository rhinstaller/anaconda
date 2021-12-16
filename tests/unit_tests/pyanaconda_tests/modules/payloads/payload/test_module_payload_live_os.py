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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import os
import tempfile
import unittest

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE, PAYLOAD_TYPE_LIVE_OS
from pyanaconda.core.util import touch
from pyanaconda.core.path import join_paths
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
from pyanaconda.modules.payloads.payload.live_os.live_os_interface import LiveOSInterface
from pyanaconda.modules.payloads.payload.live_image.installation import InstallFromImageTask

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadSharedTest


class LiveOSInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the Live OS payload."""

    def setUp(self):
        self.module = LiveOSModule()
        self.interface = LiveOSInterface(self.module)
        self.shared_tests = PayloadSharedTest(
            payload=self.module,
            payload_intf=self.interface
        )

    def _prepare_source(self):
        """Prepare a default source."""
        return self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)

    def test_type(self):
        """Test the type of the payload."""
        assert self.interface.Type == PAYLOAD_TYPE_LIVE_OS

    def test_supported_sources(self):
        """Test LiveOS supported sources API."""
        assert self.interface.SupportedSourceTypes == [SOURCE_TYPE_LIVE_OS_IMAGE]

    @patch_dbus_publish_object
    def test_set_sources(self, publisher):
        """Test if set source API of LiveOS payload."""
        sources = [self._prepare_source()]
        self.shared_tests.set_and_check_sources(sources)

    @patch_dbus_publish_object
    def test_set_multiple_sources_fail(self, publisher):
        """Test LiveOS payload can't set multiple sources."""
        sources = [self._prepare_source(), self._prepare_source()]
        self.shared_tests.set_and_check_sources(sources, exception=IncompatibleSourceError)


class LiveOSModuleTestCase(unittest.TestCase):
    """Test the Live OS payload module."""

    def setUp(self):
        self.module = LiveOSModule()

    def _create_source(self, state=SourceState.READY):
        """Create a new source with a mocked state."""
        return PayloadSharedTest.prepare_source(SourceType.LIVE_OS_IMAGE, state)

    def test_get_kernel_version_list(self):
        """Test the get_kernel_version_list method."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the image source.
            image_source = self._create_source()
            image_source._mount_point = tmp

            # Create a fake kernel file.
            os.makedirs(join_paths(tmp, "boot"))
            kernel_file = join_paths(tmp, "boot", "vmlinuz-1.2-3.x86_64")
            touch(kernel_file)

            self.module._update_kernel_version_list(image_source)

        assert self.module.get_kernel_version_list() == ["1.2-3.x86_64"]

    def test_install_with_task(self):
        """Test the install_with_tasks method."""
        source = self._create_source()
        self.module.set_sources([source])

        tasks = self.module.install_with_tasks()
        assert len(tasks) == 1
        assert isinstance(tasks[0], InstallFromImageTask)

    def test_install_with_task_no_source(self):
        """Test Live OS install with tasks with no source fail."""
        assert self.module.install_with_tasks() == []

    def test_post_install_with_tasks(self):
        """Test Live OS post installation configuration task."""
        assert self.module.post_install_with_tasks() == []
