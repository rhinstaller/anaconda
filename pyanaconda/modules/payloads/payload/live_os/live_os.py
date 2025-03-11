#
# Kickstart module for Live OS payload.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.live_image.installation import (
    InstallFromImageTask,
)
from pyanaconda.modules.payloads.payload.live_os.installation import (
    CopyTransientGnomeInitialSetupStateTask,
)
from pyanaconda.modules.payloads.payload.live_os.live_os_interface import (
    LiveOSInterface,
)
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase

log = get_module_logger(__name__)


class LiveOSModule(PayloadBase):
    """The Live OS payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveOSInterface(self)

    @property
    def type(self):
        """Type of this payload."""
        return PayloadType.LIVE_OS

    @property
    def default_source_type(self):
        """Type of the default source."""
        return SourceType.LIVE_OS_IMAGE

    @property
    def supported_source_types(self):
        """List of supported source types."""
        return [SourceType.LIVE_OS_IMAGE]

    def set_sources(self, sources):
        """Set at most one source."""
        if len(sources) > 1:
            raise IncompatibleSourceError("You can set only one source for this payload type.")

        super().set_sources(sources)

    def install_with_tasks(self):
        """Install the payload with tasks."""
        image_source = self._get_source(SourceType.LIVE_OS_IMAGE)

        tasks = []

        if not image_source:
            log.debug("No Live OS image is available.")
            return []

        install_task = InstallFromImageTask(
            sysroot=conf.target.system_root,
            mount_point=image_source.mount_point
        )

        install_task.succeeded_signal.connect(
            lambda: self._update_kernel_version_list(image_source)
        )

        tasks += [install_task]

        tasks += [CopyTransientGnomeInitialSetupStateTask(
            sysroot=conf.target.system_root,
        )]

        return tasks

    def _update_kernel_version_list(self, image_source):
        """Update the kernel versions list."""
        kernel_list = get_kernel_version_list(image_source.mount_point)
        self.set_kernel_version_list(kernel_list)
