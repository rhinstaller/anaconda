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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
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
import pytest
from unittest.mock import patch

from pyanaconda.modules.payloads.base.initialization import SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.source.factory import SourceFactory
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError, SourceSetupError
from pyanaconda.modules.payloads.constants import PayloadType, SourceType, SourceState
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import \
    PayloadSharedTest


class PayloadBaseInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.module = DNFModule()
        self.interface = DNFInterface(self.module)

        self.shared_tests = PayloadSharedTest(payload=self.module,
                                              payload_intf=self.interface)

    def test_type(self):
        self.shared_tests.check_type(PayloadType.DNF)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    def test_supported_sources(self):
        """Test supported sources API."""
        assert [SourceType.URL.value] == self.interface.SupportedSourceTypes

    def test_sources_empty(self):
        """Test sources API for emptiness."""
        self.shared_tests.check_empty_sources()

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_set_source(self, publisher):
        """Test if set source API payload."""
        sources = [self.shared_tests.prepare_source(SourceType.URL)]

        self.shared_tests.set_and_check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_add_source(self, publisher):
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
    def test_add_source_incompatible_source_failed(self, publisher):
        """Test module API to add source failed with incompatible source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.NOT_APPLICABLE)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.NFS)
        with pytest.raises(IncompatibleSourceError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_add_source_ready_failed(self, publisher):
        """Test module API to add source failed with ready source."""
        source1 = self.shared_tests.prepare_source(SourceType.URL, SourceState.READY)

        sources = [source1]
        self.shared_tests.set_and_check_sources(sources)

        source2 = self.shared_tests.prepare_source(SourceType.URL)
        with pytest.raises(SourceSetupError):
            self.module.add_source(source2)

        self.shared_tests.check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL, SourceType.NFS])
    @patch_dbus_publish_object
    def test_set_multiple_source(self, publisher):
        """Test payload setting multiple compatible sources."""
        sources = [
            self.shared_tests.prepare_source(SourceType.NFS),
            self.shared_tests.prepare_source(SourceType.URL),
            self.shared_tests.prepare_source(SourceType.URL),
        ]

        self.shared_tests.set_and_check_sources(sources)

    @patch.object(DNFModule, "supported_source_types", [SourceType.URL])
    @patch_dbus_publish_object
    def test_set_incompatible_source(self, publisher):
        """Test payload setting incompatible sources."""
        sources = [self.shared_tests.prepare_source(SourceType.LIVE_OS_IMAGE)]

        cm = self.shared_tests.set_and_check_sources(sources, exception=IncompatibleSourceError)

        msg = "Source type {} is not supported by this payload.".format(
            SourceType.LIVE_OS_IMAGE.value)
        assert str(cm.value) == msg

    @patch.object(DNFModule, "supported_source_types", [SourceType.NFS, SourceType.URL])
    @patch_dbus_publish_object
    def test_set_when_initialized_source_fail(self, publisher):
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
    def test_is_network_required(self, publisher):
        """Test IsNetworkRequired."""
        assert self.interface.IsNetworkRequired() is False

        source1 = self.shared_tests.prepare_source(SourceType.CDROM, state=SourceState.UNREADY)
        self.shared_tests.set_sources([source1])

        assert self.interface.IsNetworkRequired() is False

        source2 = self.shared_tests.prepare_source(SourceType.NFS, state=SourceState.UNREADY)
        self.shared_tests.set_sources([source1, source2])

        assert self.interface.IsNetworkRequired() is True

    @patch_dbus_publish_object
    def test_calculate_required_space(self, publisher):
        """Test CalculateRequiredTest."""
        assert self.interface.CalculateRequiredSpace() == 0

        source1 = self.shared_tests.prepare_source(SourceType.CDROM, state=SourceState.UNREADY)
        self.shared_tests.set_sources([source1])

        assert self.interface.CalculateRequiredSpace() == 0

    @patch_dbus_publish_object
    def test_set_up_sources_with_task(self, publisher):
        """Test SetUpSourcesWithTask."""
        source = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(source)

        task_path = self.interface.SetUpSourcesWithTask()
        obj = check_task_creation(task_path, publisher, SetUpSourcesTask)
        assert obj.implementation._sources == [source]

    @patch_dbus_publish_object
    def test_tear_down_sources_with_task(self, publisher):
        """Test TearDownSourcesWithTask."""
        source = SourceFactory.create_source(SourceType.CDROM)
        self.module.add_source(source)

        task_path = self.interface.TearDownSourcesWithTask()
        obj = check_task_creation(task_path, publisher, TearDownSourcesTask)
        assert obj.implementation._sources == [source]
