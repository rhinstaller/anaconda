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
import os

from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_IMAGE, INSTALL_TREE, IMAGE_DIR
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.payload.live_image.installation import VerifyImageChecksum, \
    InstallFromTarTask, InstallFromImageTask, DownloadImageTask, MountImageTask
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.modules.payloads.payload.live_image.utils import get_kernel_version_list_from_tar
from pyanaconda.modules.payloads.source.live_image.initialization import SetUpLocalImageSourceTask, \
    SetUpRemoteImageSourceTask
from pyanaconda.modules.payloads.source.utils import is_tar
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload

log = get_packaging_logger()

__all__ = ["LiveImagePayload"]


class LiveImagePayload(Payload):
    """ Install using a live filesystem image from the network """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_size = 0
        self._kernel_version_list = []
        self._install_tree_path = ""
        self.image_path = conf.target.system_root + "/disk.img"

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        if opts.proxy:
            self.data.liveimg.proxy = opts.proxy

        if not conf.payload.verify_ssl:
            self.data.liveimg.noverifyssl = not conf.payload.verify_ssl

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_LIVE_IMAGE

    def _get_source_configuration(self):
        """Get the image configuration data.

        FIXME: This is a temporary workaround.
        """
        data = LiveImageConfigurationData()

        data.url = self.data.liveimg.url or ""
        data.proxy = self.data.liveimg.proxy or ""
        data.checksum = self.data.liveimg.checksum or ""
        data.ssl_verification_enabled = not self.data.liveimg.noverifyssl

        return data

    def setup(self):
        """ Check the availability and size of the image.
        """
        source_data = self._get_source_configuration()

        if self.data.liveimg.url.startswith("file://"):
            task = SetUpLocalImageSourceTask(source_data)
        else:
            task = SetUpRemoteImageSourceTask(source_data)

        # Run the task.
        result = task.run()

        # Set up the required space.
        self._min_size = result.required_space
        log.debug("liveimg size is %s", self._min_size)

    def pre_install(self):
        """ Get image and loopback mount it.

            This is called after partitioning is setup, we now have space to
            grab the image. If it is a network source Download it to sysroot
            and provide feedback during the download (using urlgrabber
            callback).

            If it is a file:// source then use the file directly.
        """
        source_data = self._get_source_configuration()

        if self.data.liveimg.url.startswith("file://"):
            self.image_path = self.data.liveimg.url[7:]
        else:
            task = DownloadImageTask(
                configuration=source_data,
                image_path=self.image_path
            )
            task.progress_changed_signal.connect(self._progress_cb)
            task.run()

        # Verify the checksum.
        task = VerifyImageChecksum(
            image_path=self.image_path,
            checksum=self.data.liveimg.checksum
        )
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

        # Mount the image. Skip if this looks like a tarfile.
        if not is_tar(self.data.liveimg.url):
            task = MountImageTask(
                image_path=self.image_path,
                image_mount_point=INSTALL_TREE,
                iso_mount_point=IMAGE_DIR,
            )
            self._install_tree_path = task.run()

    def install(self):
        """Install the payload."""
        self._update_kernel_version_list()

        if is_tar(self.data.liveimg.url):
            task = InstallFromTarTask(
                sysroot=conf.target.system_root,
                tarfile=self.image_path
            )
        else:
            task = InstallFromImageTask(
                sysroot=conf.target.system_root,
                mount_point=self._install_tree_path
            )

        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

    def post_install(self):
        """ Unmount and remove image

            If file:// was used, just unmount it.
        """
        super().post_install()
        payload_utils.unmount(IMAGE_DIR)
        payload_utils.unmount(INSTALL_TREE)

        if os.path.exists(self.image_path) and not self.data.liveimg.url.startswith("file://"):
            os.unlink(self.image_path)

    @property
    def space_required(self):
        """ We don't know the filesystem size until it is downloaded.

            Default to 1G which should be enough for a minimal image download
            and install.
        """
        if self._min_size:
            return Size(self._min_size)
        else:
            return Size(1024 * 1024 * 1024)

    @property
    def kernel_version_list(self):
        return self._kernel_version_list

    def _update_kernel_version_list(self):
        if is_tar(self.data.liveimg.url):
            self._kernel_version_list = get_kernel_version_list_from_tar(self.image_path)
        else:
            self._kernel_version_list = get_kernel_version_list(self._install_tree_path)
