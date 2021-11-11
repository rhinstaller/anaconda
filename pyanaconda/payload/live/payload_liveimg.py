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
import glob
import os

import requests
from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_IMAGE, NETWORK_CONNECTION_TIMEOUT, \
    INSTALL_TREE, IMAGE_DIR
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.modules.payloads.payload.live_image.installation import VerifyImageChecksum, \
    InstallFromTarTask, InstallFromImageTask
from pyanaconda.modules.payloads.payload.live_image.utils import get_kernel_version_list_from_tar
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.modules.payloads.source.utils import is_tar
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.errors import PayloadInstallError, PayloadSetupError
from pyanaconda.payload.live.download_progress import DownloadProgress

log = get_packaging_logger()

__all__ = ["LiveImagePayload"]


class LiveImagePayload(Payload):
    """ Install using a live filesystem image from the network """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_size = 0
        self._proxies = {}
        self._session = util.requests_session()
        self._kernel_version_list = []
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

    def _setup_url_image(self):
        """ Check to make sure the url is available and estimate the space
            needed to download and install it.
        """
        self._proxies = {}
        if self.data.liveimg.proxy:
            try:
                proxy = ProxyString(self.data.liveimg.proxy)
                self._proxies = {"http": proxy.url,
                                 "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for liveimg --proxy=\"%s\": %s",
                         self.data.liveimg.proxy, e)

        error = None
        try:
            response = self._session.head(
                self.data.liveimg.url,
                proxies=self._proxies,
                verify=True,
                timeout=NETWORK_CONNECTION_TIMEOUT
            )

            # At this point we know we can get the image and what its size is
            # Make a guess as to minimum size needed:
            # Enough space for image and image * 3
            if response.headers.get('content-length'):
                self._min_size = int(response.headers.get('content-length')) * 4
            # FIXME: look up what is raised by Requests, replace IOError
        except IOError as e:
            log.error("Error opening liveimg: %s", e)
            error = e
        else:
            if response.status_code != 200:
                error = "http request returned %s" % response.status_code

        return error

    def _setup_file_image(self):
        """ Check to make sure the file is available and estimate the space
            needed to install it.
        """
        if not os.path.exists(self.data.liveimg.url[7:]):
            return "file does not exist: %s" % self.data.liveimg.url

        self._min_size = os.stat(self.data.liveimg.url[7:]).st_blocks * 512 * 3
        return None

    def setup(self):
        """ Check the availability and size of the image.
        """
        super().setup()

        if self.data.liveimg.url.startswith("file://"):
            error = self._setup_file_image()
        else:
            error = self._setup_url_image()

        if error:
            raise PayloadSetupError(str(error))

        log.debug("liveimg size is %s", self._min_size)

    def _pre_install_url_image(self):
        """ Download the image using Requests with progress reporting"""

        error = None
        progress = DownloadProgress()
        try:
            log.info("Starting image download")
            with open(self.image_path, "wb") as f:
                ssl_verify = not self.data.liveimg.noverifyssl
                response = self._session.get(
                    self.data.liveimg.url,
                    proxies=self._proxies,
                    verify=ssl_verify,
                    stream=True,
                    timeout=NETWORK_CONNECTION_TIMEOUT
                )
                total_length = response.headers.get('content-length')
                if total_length is None:  # no content length header
                    # just download the file in one go and fake the progress reporting once done
                    log.warning("content-length header is missing for the installation image, "
                                "download progress reporting will not be available")
                    f.write(response.content)
                    size = f.tell()
                    progress.start(self.data.liveimg.url, size)
                    progress.end(size)
                else:
                    # requests return headers as strings, so convert total_length to int
                    progress.start(self.data.liveimg.url, int(total_length))
                    bytes_read = 0
                    for buf in response.iter_content(1024 * 1024):  # 1 MB chunks
                        if buf:
                            f.write(buf)
                            f.flush()
                            bytes_read += len(buf)
                            progress.update(bytes_read)
                    progress.end(bytes_read)
                log.info("Image download finished")
        except requests.exceptions.RequestException as e:
            log.error("Error downloading liveimg: %s", e)
            error = e
        else:
            if not os.path.exists(self.image_path):
                error = "Failed to download %s, file doesn't exist" % self.data.liveimg.url
                log.error(error)

        return error

    def pre_install(self):
        """ Get image and loopback mount it.

            This is called after partitioning is setup, we now have space to
            grab the image. If it is a network source Download it to sysroot
            and provide feedback during the download (using urlgrabber
            callback).

            If it is a file:// source then use the file directly.
        """
        error = None
        if self.data.liveimg.url.startswith("file://"):
            self.image_path = self.data.liveimg.url[7:]
        else:
            error = self._pre_install_url_image()

        if error:
            raise PayloadInstallError(str(error))

        # Verify the checksum.
        task = VerifyImageChecksum(
            image_path=self.image_path,
            checksum=self.data.liveimg.checksum
        )
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

        # If this looks like a tarfile, skip trying to mount it
        if is_tar(self.data.liveimg.url):
            return

        # Work around inability to move shared filesystems.
        # Also, do not share the image mounts with /run bind-mounted to physical
        # target root during storage.mount_filesystems.
        rc = util.execWithRedirect("mount",
                                   ["--make-rprivate", "/"])
        if rc != 0:
            log.error("mount error (%s) making mount of '/' rprivate", rc)
            raise PayloadInstallError("mount error %s" % rc)

        # Mount the image and check to see if it is a LiveOS/*.img
        # style squashfs image. If so, move it to IMAGE_DIR and mount the real
        # root image on INSTALL_TREE
        rc = payload_utils.mount(self.image_path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            log.error("mount error (%s) with %s", rc, self.image_path)
            raise PayloadInstallError("mount error %s" % rc)

        # Nothing more to mount
        if not os.path.exists(INSTALL_TREE + "/LiveOS"):
            return

        # Mount the first .img in the directory on INSTALL_TREE
        img_files = glob.glob(INSTALL_TREE + "/LiveOS/*.img")
        if img_files:
            # move the mount to IMAGE_DIR
            os.makedirs(IMAGE_DIR, 0o755)
            rc = util.execWithRedirect("mount",
                                       ["--move", INSTALL_TREE, IMAGE_DIR])
            if rc != 0:
                log.error("error %s moving mount", rc)
                raise PayloadInstallError("mount error %s" % rc)

            img_file = IMAGE_DIR+"/LiveOS/" + os.path.basename(sorted(img_files)[0])
            rc = payload_utils.mount(img_file, INSTALL_TREE, fstype="auto", options="ro")
            if rc != 0:
                log.error("mount error (%s) with %s", rc, img_file)
                raise PayloadInstallError("mount error %s with %s" % (rc, img_file))

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
                mount_point=INSTALL_TREE + "/"
            )

        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

    def post_install(self):
        """ Unmount and remove image

            If file:// was used, just unmount it.
        """
        super().post_install()

        payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        if os.path.exists(IMAGE_DIR + "/LiveOS"):
            payload_utils.unmount(IMAGE_DIR, raise_exc=True)
            os.rmdir(IMAGE_DIR)

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
            self._kernel_version_list = get_kernel_version_list(INSTALL_TREE)
