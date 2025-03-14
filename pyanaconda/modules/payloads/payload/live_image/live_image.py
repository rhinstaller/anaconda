#
# Kickstart module for the live image payload.
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
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.live_image.live_image_interface import (
    LiveImageInterface,
)
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.source.factory import SourceFactory

log = get_module_logger(__name__)

__all__ = ["LiveImageModule"]


class LiveImageModule(PayloadBase):
    """The Live Image payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveImageInterface(self)

    @property
    def type(self):
        """Type of this payload."""
        return PayloadType.LIVE_IMAGE

    @property
    def default_source_type(self):
        """Type of the default source."""
        return SourceType.LIVE_IMAGE

    @property
    def supported_source_types(self):
        """Get list of sources supported by Live Image module."""
        return [
            SourceType.LIVE_IMAGE,
            SourceType.LIVE_TAR,
        ]

    def set_sources(self, sources):
        """Set at most one source."""
        if len(sources) > 1:
            raise IncompatibleSourceError("You can set only one source for this payload type.")

        super().set_sources(sources)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        source_type = SourceFactory.get_live_image_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for source in self.sources:
            source.setup_kickstart(data)

    def install_with_tasks(self):
        """Execute preparation and installation steps."""
        if not self.sources:
            log.debug("No image is available.")
            return []

        source = self.sources[0]
        tasks = source.install_with_tasks()

        self._collect_kernels_on_success(tasks)
        return tasks

    def _collect_kernels_on_success(self, tasks):
        """Collect kernel version lists from successful tasks.

        :param tasks: a list of tasks
        """
        for task in tasks:
            task.succeeded_signal.connect(
                lambda t=task: self.set_kernel_version_list(t.get_result())
            )
