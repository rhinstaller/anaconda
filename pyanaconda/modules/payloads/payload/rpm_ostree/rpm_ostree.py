#
# Kickstart module for the RPM OSTree payload.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
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
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree_interface import (
    RPMOSTreeInterface,
)
from pyanaconda.modules.payloads.source.factory import SourceFactory

log = get_module_logger(__name__)


class RPMOSTreeModule(PayloadBase):
    """The RPM OSTree payload module."""

    def __init__(self):
        super().__init__()
        self._internal_mounts = []

        # Don't provide the kernel version list. This
        # payload handles the bootloader configuration.
        self.set_kernel_version_list([])

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RPMOSTreeInterface(self)

    @property
    def type(self):
        """Type of the payload."""
        return PayloadType.RPM_OSTREE

    @property
    def default_source_type(self):
        """Type of the default source."""
        return SourceType.RPM_OSTREE

    @property
    def supported_source_types(self):
        """Get list of sources supported by the RPM OSTree module."""
        return [
            SourceType.RPM_OSTREE,
            SourceType.RPM_OSTREE_CONTAINER,
            SourceType.FLATPAK,
        ]

    def process_kickstart(self, data):
        """Process the kickstart data."""
        source_type = SourceFactory.get_rpm_ostree_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for source in self.sources:
            source.setup_kickstart(data)

    def _get_ostree_source(self):
        """Get source for RPM OSTree.

        Find out if we need OSTree repo or container source type.
        """
        return self._get_source(SourceType.RPM_OSTREE_CONTAINER) or \
            self._get_source(SourceType.RPM_OSTREE)

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        ostree_source = self._get_ostree_source()

        if not ostree_source:
            log.debug("No OSTree RPM source is available.")
            return []

        data = ostree_source.configuration

        tasks = [
            InitOSTreeFsAndRepoTask(
                physroot=conf.target.physical_root
            ),
            ChangeOSTreeRemoteTask(
                data=data,
                physroot=conf.target.physical_root
            )
        ]

        # separate pulling of the container will be handled by deployment on the container
        # otherwise handled by Deploy task
        if not data.is_container():
            tasks.append(
                PullRemoteAndDeleteTask(
                    data=data,
                ))

        tasks += [
            DeployOSTreeTask(
                data=data,
                physroot=conf.target.physical_root
            ),
            SetSystemRootTask(
                physroot=conf.target.physical_root
            ),
            CopyBootloaderDataTask(
                physroot=conf.target.physical_root,
                sysroot=conf.target.system_root
            ),
            PrepareOSTreeMountTargetsTask(
                data=data,
                physroot=conf.target.physical_root,
                sysroot=conf.target.system_root
            )
        ]

        flatpak_source = self._get_source(SourceType.FLATPAK)

        if flatpak_source:
            task = InstallFlatpaksTask(
                sysroot=conf.target.system_root
            )
            tasks.append(task)

        self._collect_mount_points_on_success(tasks)
        return tasks

    def _collect_mount_points_on_success(self, tasks):
        """Collect mount points from successful tasks.

        Ignore tasks that doesn't return a list of mount points.

        :param tasks: a list of tasks
        """
        for task in tasks:
            if isinstance(task, PrepareOSTreeMountTargetsTask):
                task.succeeded_signal.connect(
                    lambda t=task: self._add_internal_mounts(t.get_result())
                )

    def _add_internal_mounts(self, mount_points):
        """Add mount points that will have to be unmounted.

        :param mount_points: a list of mount points
        """
        self._internal_mounts.extend(mount_points)
        log.debug("Internal mounts are set to: %s", self._internal_mounts)

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        ostree_source = self._get_ostree_source()

        if not ostree_source:
            log.debug("No OSTree RPM source is available.")
            return []

        return [
            ChangeOSTreeRemoteTask(
                data=ostree_source.configuration,
                sysroot=conf.target.system_root
            ),
            ConfigureBootloader(
                sysroot=conf.target.system_root,
            )
        ]

    def tear_down_with_tasks(self):
        """Returns teardown tasks for this payload.

        Clean up everything after this payload.

        :return: a list of tasks
        """
        tasks = super().tear_down_with_tasks()

        tasks.append(
            TearDownOSTreeMountTargetsTask(
                mount_points=self._internal_mounts
            )
        )

        return tasks
