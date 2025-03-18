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
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.live_image.live_image_interface import \
    LiveImageInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["LiveImageModule"]


class LiveImageModule(PayloadBase):
    """The Live Image payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveImageInterface(self)

    @property
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return PayloadType.LIVE_IMAGE

    @property
    def supported_source_types(self):
        """Get list of sources supported by Live Image module."""
        return [
            SourceType.LIVE_IMAGE
        ]

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

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        * Download the image
        * Check the checksum
        * Mount the image
        """
        # task = SetupInstallationSourceImageTask(
        #     self.url,
        #     self.proxy,
        #     self.checksum,
        #     self.verifyssl,
        #     self.image_path,
        #     INSTALL_TREE,
        #     self.requests_session
        # )
        # task.succeeded_signal.connect(lambda: self.set_image_path(task.get_result()))
        # return [task]
        return []

    def post_install_with_tasks(self):
        """Execute post installation steps.

        * Copy Driver Disk files to the resulting system
        """
        # return [
        #     CopyDriverDisksFilesTask(conf.target.system_root)
        # ]
        return []

    def install_with_tasks(self):
        """Install the payload."""
        # if url_target_is_tarfile(self._url):
        #     task = InstallFromTarTask(
        #         self.image_path,
        #         conf.target.system_root,
        #         self.kernel_version_list
        #     )
        # else:
        #     task = InstallFromImageTask(
        #         conf.target.system_root,
        #         self.kernel_version_list
        #     )
        #
        # task2 = TeardownInstallationSourceImageTask(
        #     self.image_path,
        #     self.url,
        #     INSTALL_TREE
        # )
        #
        # return [task, task2]
        return []
