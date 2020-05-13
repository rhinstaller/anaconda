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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
# This test will test PayloadBase with interface but it's much easier to test
# this with an existing payload so use DNF just as dummy test payload.
#
import unittest
from unittest.mock import patch

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object
from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest

from pyanaconda.modules.common.errors.payload import IncompatibleSourceError, SourceSetupError
from pyanaconda.modules.payloads.constants import PayloadType, SourceType, SourceState
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface


class PayloadBaseInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = DNFModule()
        self.interface = DNFInterface(self.module)

        self.shared_tests = PayloadSharedTest(self,
                                              payload=self.module,
                                              payload_intf=self.interface)

    def type_test(self):
        self.shared_tests.check_type(PayloadType.DNF)

    def required_space_test(self):
        """Test required space."""
        self.module._required_space = 100

        self.assertEqual(self.interface.RequiredSpace, 100)

    def required_default_space_test(self):
        """Test default value for required space.

        This is used when space is not known.
        """
        self.module._required_space = None

        self.assertEqual(self.interface.RequiredSpace, self.module.default_required_space)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    def supported_sources_test(self):
        """Test supported sources API."""
        self.assertEqual(
            [SourceType.URL.value],
            self.interface.SupportedSourceTypes)

    def sources_empty_test(self):
        """Test sources API for emptiness."""
        self.shared_tests.check_empty_sources()

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def set_source_test(self, publisher):
        """Test if set source API payload."""
        sources = [self.shared_tests.prepare_source(SourceType.URL)]

        self.shared_tests.set_and_check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def add_source_test(self, publisher):
        """Test module API to add source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.NOT_APPLICABLE)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.URL)
        self.module.add_source(source2)

        sources.append(source2)
        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def add_source_incompatible_source_failed_test(self, publisher):
        """Test module API to add source failed with incompatible source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.NOT_APPLICABLE)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.NFS)
        with self.assertRaises(IncompatibleSourceError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def add_source_ready_failed_test(self, publisher):
        """Test module API to add source failed with ready source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.READY)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.URL)
        with self.assertRaises(SourceSetupError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL, SourceType.NFS])
    @patch_dbus_publish_object
    def set_multiple_source_test(self, publisher):
        """Test payload setting multiple compatible sources."""
        sources = [
            self.shared_tests.prepare_source(SourceType.NFS),
            self.shared_tests.prepare_source(SourceType.URL),
            self.shared_tests.prepare_source(SourceType.URL),
        ]

        self.shared_tests.set_and_check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def set_incompatible_source_test(self, publisher):
        """Test payload setting incompatible sources."""
        sources = [self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)]

        cm = self.shared_tests.set_and_check_sources(sources, exception=IncompatibleSourceError)

        msg = "Source type {} is not supported by this payload.".format(
            SourceType.LIVE_OS_IMAGE.value)
        self.assertEqual(str(cm.exception), msg)

    @patch.object(DNFModule, "supported_source_types", [SourceType.NFS, SourceType.URL])
    @patch_dbus_publish_object
    def set_when_initialized_source_fail_test(self, publisher):
        """Test payload can't set new sources if the old ones are initialized."""
        source1 = self.shared_tests.prepare_source(SourceType.NFS)
        source2 = self.shared_tests.prepare_source(SourceType.URL, state=SourceState.NOT_APPLICABLE)

        self.shared_tests.set_and_check_sources([source1])

        # can't switch source if attached source is ready
        source1.get_state.return_value = SourceState.READY
        self.shared_tests.set_sources([source2], SourceSetupError)
        self.shared_tests.check_sources([source1])

        # change to source2 when attached source state is UNREADY
        source1.get_state.return_value = SourceState.UNREADY
        self.shared_tests.set_and_check_sources([source2])

        # can change back anytime because source2 has state NOT_APPLICABLE
        self.shared_tests.set_and_check_sources([source1])

    @patch_dbus_publish_object
    def is_network_required_test(self, publisher):
        """Test IsNetworkRequired."""
        self.assertEqual(self.interface.IsNetworkRequired(), False)

        source1 = self.shared_tests.prepare_source(SourceType.CDROM, state=SourceState.UNREADY)
        self.shared_tests.set_sources([source1])

        self.assertEqual(self.interface.IsNetworkRequired(), False)

        source2 = self.shared_tests.prepare_source(SourceType.NFS, state=SourceState.UNREADY)
        self.shared_tests.set_sources([source1, source2])

        self.assertEqual(self.interface.IsNetworkRequired(), True)
