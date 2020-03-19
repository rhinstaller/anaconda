#
# Kickstart module for Live Image payload.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os

from pyanaconda.core.signal import Signal
from pyanaconda.core.util import requests_session
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE

from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.base.initialization import CopyDriverDisksFilesTask, \
    UpdateBLSConfigurationTask
from pyanaconda.modules.payloads.base.installation import InstallFromImageTask
from pyanaconda.modules.payloads.base.utils import get_kernel_version_list
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.live_image.live_image_interface import \
    LiveImageInterface
from pyanaconda.modules.payloads.payload.live_image.initialization import \
    CheckInstallationSourceImageTask, SetupInstallationSourceImageTask, \
    TeardownInstallationSourceImageTask
from pyanaconda.modules.payloads.payload.live_image.installation import InstallFromTarTask
from pyanaconda.modules.payloads.payload.live_image.utils import \
    get_kernel_version_list_from_tar, url_target_is_tarfile

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveImageModule(PayloadBase):
    """The Live Image payload module."""

    def __init__(self):
        super().__init__()
        self._url = ""
        self.url_changed = Signal()

        self._proxy = ""
        self.proxy_changed = Signal()

        self._checksum = ""
        self.checksum_changed = Signal()

        self._verifyssl = True
        self.verifyssl_changed = Signal()

        self._kernel_version_list = []
        self.kernel_version_list_changed = Signal()

        self._image_path = conf.target.system_root + "/disk.img"

        self._requests_session = None

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
    def default_required_space(self):
        """Get 1G as default when the value is not known."""
        return 1024 * 1024 * 1024

    @property
    def supported_source_types(self):
        """Get list of sources supported by Live Image module."""
        # TODO: Add supported sources when implemented
        return None

    def process_kickstart(self, data):
        """Process the kickstart data."""
        liveimg = data.liveimg

        self.set_url(liveimg.url)
        self.set_proxy(liveimg.proxy)
        self.set_checksum(liveimg.checksum)

        if liveimg.noverifyssl:
            self.set_verifyssl(not liveimg.noverifyssl)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        liveimg = data.liveimg
        liveimg.url = self.url
        liveimg.proxy = self.proxy
        liveimg.checksum = self.checksum
        liveimg.noverifyssl = not self.verifyssl
        liveimg.seen = True

    @property
    def url(self):
        """Get url where to obtain the live image for installation.

        :rtype: str
        """
        return self._url

    def set_url(self, url):
        self._url = url or ""
        self.url_changed.emit()
        log.debug("Liveimg url is set to '%s'", self._url)

    @property
    def proxy(self):
        """Get proxy setting which should be use to obtain the image.

        :rtype: str
        """
        return self._proxy

    def set_proxy(self, proxy):
        self._proxy = proxy or ""
        self.proxy_changed.emit()
        log.debug("Liveimg proxy is set to '%s'", self._proxy)

    @property
    def checksum(self):
        """Get checksum of the image for verification.

        :rtype: str
        """
        return self._checksum

    def set_checksum(self, checksum):
        self._checksum = checksum or ""
        self.checksum_changed.emit()
        log.debug("Liveimg checksum is set to '%s'", self._checksum)

    @property
    def verifyssl(self):
        """Get should ssl verification be enabled?

        :rtype: bool
        """
        return self._verifyssl

    def set_verifyssl(self, verifyssl):
        self._verifyssl = verifyssl
        self.verifyssl_changed.emit()
        log.debug("Liveimg ssl verification is set to '%s'", self._verifyssl)

    @property
    def image_path(self):
        """Get source image file path.

        :rtype: str
        """
        return self._image_path

    def set_image_path(self, image_path):
        """Set source image file path."""
        self._image_path = image_path
        log.debug("Source image file path is set to '%s'", self._image_path)

    @property
    def requests_session(self):
        """Get requests session."""
        # FIXME: share in Payload module?
        if not self._requests_session:
            self._requests_session = requests_session()
        return self._requests_session

    def update_kernel_version_list(self):
        """Update list of kernel versions."""
        if url_target_is_tarfile(self._url):
            if not os.path.exists(self.image_path):
                raise SourceSetupError("Failed to find tarfile image")
            kernel_version_list = get_kernel_version_list_from_tar(self.image_path)
        else:
            kernel_version_list = get_kernel_version_list(INSTALL_TREE)

        self.set_kernel_version_list(kernel_version_list)

    @property
    def kernel_version_list(self):
        """Get list of kernel versions."""
        return self._kernel_version_list

    def set_kernel_version_list(self, kernel_version_list):
        """Set list of kernel versions."""
        self._kernel_version_list = kernel_version_list
        self.kernel_version_list_changed.emit(self._kernel_version_list)
        log.debug("List of kernel versions is set to '%s'", self._kernel_version_list)

    def setup_with_task(self):
        """Check availability of the image and update required space."""
        task = CheckInstallationSourceImageTask(
            self.url,
            self.proxy,
            self.requests_session
        )
        task.succeeded_signal.connect(lambda: self.set_required_space(task.get_result()))
        return task

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        * Download the image
        * Check the checksum
        * Mount the image
        """
        task = SetupInstallationSourceImageTask(
            self.url,
            self.proxy,
            self.checksum,
            self.verifyssl,
            self.image_path,
            INSTALL_TREE,
            self.requests_session
        )
        task.succeeded_signal.connect(lambda: self.set_image_path(task.get_result()))
        return [task]

    def post_install_with_tasks(self):
        """Execute post installation steps.

        * Update bootloader BLS configuration
        * Copy Driver Disk files to the resulting system
        """
        return [
            UpdateBLSConfigurationTask(
                conf.target.system_root,
                self.kernel_version_list
            ),
            CopyDriverDisksFilesTask(conf.target.system_root)
        ]

    def install_with_tasks(self):
        """Install the payload."""
        if url_target_is_tarfile(self._url):
            task = InstallFromTarTask(
                self.image_path,
                conf.target.system_root,
                self.kernel_version_list
            )
        else:
            task = InstallFromImageTask(
                conf.target.system_root,
                self.kernel_version_list
            )

        return [task]

    def teardown_with_task(self):
        """Tear down installation source image.

        * Unmount the image
        * Clean up mount point directories
        * Remove downloaded image
        """
        return TeardownInstallationSourceImageTask(
            self.image_path,
            self.url,
            INSTALL_TREE
        )

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        # TODO: Replace SetupInstallationSourceImageTask with SetUpSourcesTask here
        pass

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        # TODO: Replace TeardownInstallationSourceImageTask with TearDownSourcesTask here
        pass
