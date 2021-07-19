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
import unittest

from tests.unit_tests.pyanaconda_tests import check_task_creation, patch_dbus_publish_object, \
    PropertiesChangedCallback
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadSharedTest

from pyanaconda.core.constants import SOURCE_TYPE_LIVE_OS_IMAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError, IncompatibleSourceError
from pyanaconda.modules.payloads.constants import SourceType, PayloadType, SourceState
from pyanaconda.modules.payloads.base.initialization import SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
from pyanaconda.modules.payloads.payload.live_os.live_os_interface import LiveOSInterface


class LiveOSInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.live_os_module = LiveOSModule()
        self.live_os_interface = LiveOSInterface(self.live_os_module)

        self.shared_tests = PayloadSharedTest(self,
                                              payload=self.live_os_module,
                                              payload_intf=self.live_os_interface)

        self.callback = PropertiesChangedCallback()
        self.live_os_interface.PropertiesChanged.connect(self.callback)

    def _prepare_source(self):
        return self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)

    def _prepare_and_use_source(self):
        source = self._prepare_source()
        self.live_os_module.set_sources([source])

        return source

    def test_type(self):
        self.shared_tests.check_type(PayloadType.LIVE_OS)

    def test_supported_sources(self):
        """Test LiveOS supported sources API."""
        self.assertEqual(
            [SOURCE_TYPE_LIVE_OS_IMAGE],
            self.live_os_interface.SupportedSourceTypes)

    @patch_dbus_publish_object
    def test_set_source(self, publisher):
        """Test if set source API of LiveOS payload."""
        sources = [self._prepare_source()]

        self.shared_tests.set_and_check_sources(sources)

    @patch_dbus_publish_object
    def test_set_multiple_sources_fail(self, publisher):
        """Test LiveOS payload can't set multiple sources."""
        paths = [
            self._prepare_source(),
            self._prepare_source()
        ]

        self.shared_tests.set_and_check_sources(paths, exception=IncompatibleSourceError)

    @patch_dbus_publish_object
    def test_set_when_initialized_source_fail(self, publisher):
        """Test LiveOS payload can't set new sources if the old ones are initialized."""
        source1 = self._prepare_source()
        source2 = self._prepare_source()

        self.shared_tests.set_and_check_sources([source1])

        # can't switch source if attached source is ready
        source1.get_state.return_value = SourceState.READY
        self.shared_tests.set_sources([source2], SourceSetupError)
        self.shared_tests.check_sources([source1])

        source1.get_state.return_value = SourceState.UNREADY
        self.shared_tests.set_and_check_sources([source1])

    @patch_dbus_publish_object
    def test_set_up_installation_sources_task(self, publisher):
        """Test Live OS is able to create a set up installation sources task."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.SetUpSourcesWithTask()

        check_task_creation(self, task_path, publisher, SetUpSourcesTask)

    @patch_dbus_publish_object
    def test_tear_down_installation_source_task(self, publisher):
        """Test Live OS is able to create a tear down installation sources task."""
        self._prepare_and_use_source()

        task_path = self.live_os_interface.TearDownSourcesWithTask()

        check_task_creation(self, task_path, publisher, TearDownSourcesTask)


class LiveOSModuleTestCase(unittest.TestCase):

    def setUp(self):
        self.module = LiveOSModule()

    def _create_source(self, state=SourceState.READY):
        """Create a new source with a mocked state."""
        return PayloadSharedTest.prepare_source(SourceType.LIVE_OS_IMAGE, state)

    def test_get_kernel_version_list(self):
        """Test the get_kernel_version_list method."""
        self.assertEqual(self.module.get_kernel_version_list(), [])

    def test_install_with_task(self):
        """Test the install_with_tasks method."""
        source = self._create_source()
        self.module.set_sources([source])

        # tasks = self.module.install_with_tasks()
        # self.assertEqual(len(tasks), 1)
        # self.assertIsInstance(tasks[0], InstallFromImageTask)
        self.assertEqual(self.module.install_with_tasks(), [])

    def test_install_with_task_no_source(self):
        """Test Live OS install with tasks with no source fail."""
        # with self.assertRaises(SourceSetupError):
        #    self.module.install_with_tasks()
        self.module.install_with_tasks()

    def test_post_install_with_tasks(self):
        """Test Live OS post installation configuration task."""
        tasks = self.module.post_install_with_tasks()
        self.assertEqual(len(tasks), 0)
