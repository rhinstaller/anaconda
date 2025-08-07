#
# Copyright (C) 2024  Red Hat, Inc.
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
import unittest

from pyanaconda.core.constants import (
    PAYLOAD_TYPE_BOOTC,
    SOURCE_TYPE_BOOTC,
)
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.bootc.bootc import BootcModule
from pyanaconda.modules.payloads.payload.bootc.bootc_interface import BootcInterface
from pyanaconda.modules.payloads.payload.bootc.installation import DeployBootcTask
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests import check_instances
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadKickstartSharedTest,
)


class BootcInterfaceTestCase(unittest.TestCase):
    """Test the Bootc DBus module."""

    def setUp(self):
        self.module = BootcModule()
        self.interface = BootcInterface(self.module)

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == PAYLOAD_TYPE_BOOTC

    def test_default_source_type(self):
        """Test the DefaultSourceType property."""
        assert self.interface.DefaultSourceType == SOURCE_TYPE_BOOTC

    def test_supported_sources(self):
        """Test the SupportedSourceTypes property."""
        assert self.interface.SupportedSourceTypes == [
            SOURCE_TYPE_BOOTC,
        ]


class BootcKickstartTestCase(unittest.TestCase):
    """Test the Bootc kickstart commands."""

    def setUp(self):
        self.maxDiff = None
        self.module = PayloadsService()
        self.interface = PayloadsInterface(self.module)
        self.shared_ks_tests = PayloadKickstartSharedTest(
            payload_service=self.module,
            payload_service_intf=self.interface
        )

    def _check_properties(self, expected_source_type):
        payload = self.shared_ks_tests.get_payload()
        assert isinstance(payload, BootcModule)

        if expected_source_type is None:
            assert not payload.sources
        else:
            sources = payload.sources
            assert len(sources) == 1
            assert sources[0].type.value == expected_source_type

    def test_bootc_kickstart(self):
        ks_in = """
        bootc --source-imgref=quay.io/centos-bootc/centos-bootc:stream9 --stateroot=default
        """
        ks_out = """
        # Bootc setup
        bootc --stateroot="default" --source-imgref="quay.io/centos-bootc/centos-bootc:stream9" --target-imgref="quay.io/centos-bootc/centos-bootc:stream9"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_BOOTC)


class BootcModuleTestCase(unittest.TestCase):
    """Test the Bootc module."""

    def setUp(self):
        self.maxDiff = None
        self.module = BootcModule()

    def test_get_kernel_version_list(self):
        """Test the get_kernel_version_list method."""
        assert self.module.get_kernel_version_list() == []

    def test_install_with_tasks(self):
        """Test the install_with_tasks method."""
        assert self.module.install_with_tasks() == []

        bootc_source = SourceFactory.create_source(SourceType.BOOTC)
        self.module.set_sources([bootc_source])

        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            DeployBootcTask,
        ])
