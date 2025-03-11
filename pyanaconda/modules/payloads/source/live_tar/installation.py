#
# Copyright (C) 2021 Red Hat, Inc.
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
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.live_image.installation import (
    DownloadImageTask,
    InstallFromTarTask,
    RemoveImageTask,
    VerifyImageChecksumTask,
)
from pyanaconda.modules.payloads.payload.live_image.utils import (
    get_kernel_version_list_from_tar,
)

__all__ = ["InstallLiveTarTask"]


class InstallLiveTarTask(Task):
    """Task for the complete live tarball installation."""

    def __init__(self, sysroot, configuration: LiveImageConfigurationData):
        """Create a new task.

        :param str sysroot: a path to the system root
        :param configuration: a configuration of an image
        :type configuration: LiveImageConfigurationData
        """
        super().__init__()
        self._sysroot = sysroot
        self._configuration = configuration
        self._kernel_version_list = []
        self._download_path = self._sysroot + "/source.tar"
        self._tarball_path = None

    @property
    def name(self):
        """The name of the task."""
        return "Install a live tarball"

    def run(self):
        """Run the task.

        :return: a list of kernel versions
        """
        self._set_up_tarball()
        self._collect_kernels()
        self._install_tarball()
        self._tear_down_tarball()

        return self._kernel_version_list

    def _set_up_tarball(self):
        """Set up the tarball for the installation.

        Download and verify the tarball.
        """
        task = DownloadImageTask(
            configuration=self._configuration,
            download_path=self._download_path
        )
        self._tarball_path = self._run_task(task)

        task = VerifyImageChecksumTask(
            configuration=self._configuration,
            image_path=self._tarball_path
        )
        self._run_task(task)

    def _install_tarball(self):
        """Install the content of the tarball."""
        task = InstallFromTarTask(
            sysroot=self._sysroot,
            tarfile=self._tarball_path
        )
        self._run_task(task)

    def _collect_kernels(self):
        """Collect the kernel version list."""
        self._kernel_version_list = get_kernel_version_list_from_tar(
            self._tarball_path
        )

    def _tear_down_tarball(self):
        """Tear down the tarball after the installation."""
        task = RemoveImageTask(self._download_path)
        self._run_task(task)

    def _run_task(self, task):
        """Run a subtask."""
        task.progress_changed_signal.connect(
            self._handle_progress_changed
        )
        return task.run()

    def _handle_progress_changed(self, step, message):
        """Handle a progress report of a subtask."""
        self.report_progress(message)
