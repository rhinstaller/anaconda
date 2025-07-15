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
import unittest

from pyanaconda.core.constants import (
    PAYLOAD_TYPE_RPM_OSTREE,
    SOURCE_TYPE_BOOTC,
    SOURCE_TYPE_FLATPAK,
    SOURCE_TYPE_RPM_OSTREE,
    SOURCE_TYPE_RPM_OSTREE_CONTAINER,
)
from pyanaconda.modules.payloads.base.initialization import TearDownSourcesTask
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_installation import (
    InstallFlatpaksTask,
)
from pyanaconda.modules.payloads.payload.rpm_ostree.installation import (
    ChangeOSTreeRemoteTask,
    ConfigureBootloader,
    CopyBootloaderDataTask,
    DeployOSTreeTask,
    InitOSTreeFsAndRepoTask,
    PrepareOSTreeMountTargetsTask,
    PullRemoteAndDeleteTask,
    SetSystemRootTask,
    TearDownOSTreeMountTargetsTask,
)
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree import RPMOSTreeModule
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree_interface import (
    RPMOSTreeInterface,
)
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests import check_instances
from tests.unit_tests.pyanaconda_tests.modules.payloads.payload.module_payload_shared import (
    PayloadKickstartSharedTest,
)


class RPMOSTreeInterfaceTestCase(unittest.TestCase):
    """Test the RPM OSTree DBus module."""

    def setUp(self):
        self.module = RPMOSTreeModule()
        self.interface = RPMOSTreeInterface(self.module)

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == PAYLOAD_TYPE_RPM_OSTREE

    def test_default_source_type(self):
        """Test the DefaultSourceType property."""
        assert self.interface.DefaultSourceType == SOURCE_TYPE_RPM_OSTREE

    def test_supported_sources(self):
        """Test the SupportedSourceTypes property."""
        assert self.interface.SupportedSourceTypes == [
            SOURCE_TYPE_RPM_OSTREE,
            SOURCE_TYPE_RPM_OSTREE_CONTAINER,
            SOURCE_TYPE_FLATPAK,
            SOURCE_TYPE_BOOTC,
        ]


class RPMOSTreeKickstartTestCase(unittest.TestCase):
    """Test the RPM OSTree kickstart commands."""

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
        assert isinstance(payload, RPMOSTreeModule)

        if expected_source_type is None:
            assert not payload.sources
        else:
            sources = payload.sources
            assert len(sources) == 1
            assert sources[0].type.value == expected_source_type

    def test_ostree_kickstart(self):
        ks_in = """
        ostreesetup --osname="fedora-atomic" --remote="fedora-atomic-28" --url="file:///ostree/repo" --ref="fedora/28/x86_64/atomic-host" --nogpg
        """
        ks_out = """
        # OSTree setup
        ostreesetup --osname="fedora-atomic" --remote="fedora-atomic-28" --url="file:///ostree/repo" --ref="fedora/28/x86_64/atomic-host" --nogpg
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE)

    def test_ostree_container_kickstart(self):
        ks_in = """
        ostreecontainer --stateroot="fedora-coreos" --transport="repository" --remote="fedora" --url="quay.io/fedora/coreos:stable" --no-signature-verification
        """
        ks_out = """
        # OSTree container setup
        ostreecontainer --stateroot="fedora-coreos" --remote="fedora" --no-signature-verification --transport="repository" --url="quay.io/fedora/coreos:stable"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE_CONTAINER)

    def test_priority_kickstart(self):
        ks_in = """
        ostreesetup --osname="fedora-iot" --url="https://compose/iot/" --ref="fedora/iot"
        url --url="https://compose/Everything"
        """
        ks_out = """
        # OSTree setup
        ostreesetup --osname="fedora-iot" --remote="fedora-iot" --url="https://compose/iot/" --ref="fedora/iot"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE)

    def test_ostreecontainer_priority_kickstart(self):
        ks_in = """
        url --url="https://compose/Everything"
        ostreecontainer --stateroot="fedora-coreos" --remote="fedora" --url="quay.io/fedora/coreos:stable"
        """
        ks_out = """
        # OSTree container setup
        ostreecontainer --stateroot="fedora-coreos" --remote="fedora" --url="quay.io/fedora/coreos:stable"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE_CONTAINER)


class RPMOSTreeModuleTestCase(unittest.TestCase):
    """Test the RPM OSTree module."""

    def setUp(self):
        self.maxDiff = None
        self.module = RPMOSTreeModule()

    def test_get_kernel_version_list(self):
        """Test the get_kernel_version_list method."""
        assert self.module.get_kernel_version_list() == []

    def test_install_with_tasks(self):
        """Test the install_with_tasks method."""
        assert self.module.install_with_tasks() == []

        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE)
        self.module.set_sources([rpm_source])

        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            InitOSTreeFsAndRepoTask,
            ChangeOSTreeRemoteTask,
            PullRemoteAndDeleteTask,
            DeployOSTreeTask,
            SetSystemRootTask,
            CopyBootloaderDataTask,
            PrepareOSTreeMountTargetsTask,
        ])

        rpm_container_source = SourceFactory.create_source(SourceType.RPM_OSTREE_CONTAINER)
        self.module.set_sources([rpm_container_source])

        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            InitOSTreeFsAndRepoTask,
            ChangeOSTreeRemoteTask,
            DeployOSTreeTask,
            SetSystemRootTask,
            CopyBootloaderDataTask,
            PrepareOSTreeMountTargetsTask,
        ])

        flatpak_source = SourceFactory.create_source(SourceType.FLATPAK)
        self.module.set_sources([rpm_source, flatpak_source])

        tasks = self.module.install_with_tasks()
        check_instances(tasks, [
            InitOSTreeFsAndRepoTask,
            ChangeOSTreeRemoteTask,
            PullRemoteAndDeleteTask,
            DeployOSTreeTask,
            SetSystemRootTask,
            CopyBootloaderDataTask,
            PrepareOSTreeMountTargetsTask,
            InstallFlatpaksTask,
        ])

    def test_collect_mount_points(self):
        """Collect mount points from successful tasks."""
        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE)
        self.module.set_sources([rpm_source])
        tasks = self.module.install_with_tasks()

        for task in tasks:
            # Fake the task results.
            task_id = task.__class__.__name__
            task._set_result([
                "/path/{}/1".format(task_id),
                "/path/{}/2".format(task_id)
            ])

            # Fake the task run.
            task.succeeded_signal.emit()

        assert self.module._internal_mounts == [
            "/path/PrepareOSTreeMountTargetsTask/1",
            "/path/PrepareOSTreeMountTargetsTask/2"
        ]

    def test_container_collect_mount_points(self):
        """Collect mount points from successful tasks with ostreecontainer."""
        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE_CONTAINER)
        self.module.set_sources([rpm_source])
        tasks = self.module.install_with_tasks()

        for task in tasks:
            # Fake the task results.
            task_id = task.__class__.__name__
            task._set_result([
                "/path/{}/1".format(task_id),
                "/path/{}/2".format(task_id)
            ])

            # Fake the task run.
            task.succeeded_signal.emit()

        assert self.module._internal_mounts == [
            "/path/PrepareOSTreeMountTargetsTask/1",
            "/path/PrepareOSTreeMountTargetsTask/2"
        ]

    def test_post_install_with_tasks(self):
        """Test the post_install_with_tasks method."""
        assert self.module.post_install_with_tasks() == []

        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE)
        self.module.set_sources([rpm_source])

        tasks = self.module.post_install_with_tasks()
        check_instances(tasks, [
            ChangeOSTreeRemoteTask,
            ConfigureBootloader,
        ])

    def test_container_post_install_with_tasks(self):
        """Test the post_install_with_tasks method with ostreecontainer."""
        assert self.module.post_install_with_tasks() == []

        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE_CONTAINER)
        self.module.set_sources([rpm_source])

        tasks = self.module.post_install_with_tasks()
        check_instances(tasks, [
            ChangeOSTreeRemoteTask,
            ConfigureBootloader,
        ])

    def test_tear_down_with_tasks(self):
        """Test the tear_down_with_tasks method."""
        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE)

        self.module.set_sources([rpm_source])
        self.module._add_internal_mounts(["/path/1", "/path/2"])

        tasks = self.module.tear_down_with_tasks()

        check_instances(tasks, [
            TearDownSourcesTask,
            TearDownOSTreeMountTargetsTask
        ])

        assert tasks[0]._sources == [rpm_source]
        assert tasks[1]._internal_mounts == ["/path/1", "/path/2"]

    def test_container_tear_down_with_tasks(self):
        """Test the tear_down_with_tasks method with ostreecontainer."""
        rpm_source = SourceFactory.create_source(SourceType.RPM_OSTREE_CONTAINER)

        self.module.set_sources([rpm_source])
        self.module._add_internal_mounts(["/path/1", "/path/2"])

        tasks = self.module.tear_down_with_tasks()

        check_instances(tasks, [
            TearDownSourcesTask,
            TearDownOSTreeMountTargetsTask
        ])

        assert tasks[0]._sources == [rpm_source]
        assert tasks[1]._internal_mounts == ["/path/1", "/path/2"]
