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
import glob
import hashlib
import os

from requests.exceptions import RequestException

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import IMAGE_DIR, NETWORK_CONNECTION_TIMEOUT
from pyanaconda.core.util import execWithRedirect, lowerASCII
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.payload.live_image.utils import (
    get_local_image_path_from_url,
    get_proxies_from_option,
    url_target_is_tarfile,
)
from pyanaconda.payload.utils import mount, unmount

log = get_module_logger(__name__)


class SetupInstallationSourceImageTask(Task):
    """Task to set up source image for installation.

    * Download the image if it is remote.
    * Check the checksum.
    * Mount the image.
    """

    def __init__(self, url, proxy, checksum, noverifyssl, image_path, image_mount_point, session):
        """Create a new task.

        :param url: installation source image url
        :type url: str
        :param proxy: proxy to be used to fetch the image
        :type proxy: str
        :param checksum: checksum of the image
        :type checksum: str
        :param image_path: destination path for image download
        :type image_path: str
        :param image_mount_point: Mount point of the source image
        :type image_mount_point: str
        :param session: Requests session for image download
        :type session:
        """
        super().__init__()
        self._url = url
        self._proxy = proxy
        self._checksum = checksum
        self._noverifyssl = noverifyssl
        self._image_path = image_path
        self._session = session
        self._image_mount_point = image_mount_point

    @property
    def name(self):
        return "Set up installation source image."

    def _download_image(self, url, image_path, session):
        """Download the image using Requests with progress reporting"""
        error = None
        try:
            log.info("Starting image download")
            with open(image_path, "wb") as f:
                ssl_verify = not self._noverifyssl
                proxies = get_proxies_from_option(self._proxy)
                response = session.get(url, proxies=proxies, verify=ssl_verify, stream=True,
                                       timeout=NETWORK_CONNECTION_TIMEOUT)
                total_length = response.headers.get('content-length')
                if total_length is None:
                    # just download the file in one go and fake the progress reporting once done
                    log.warning("content-length header is missing for the installation image, "
                                "download progress reporting will not be available")
                    f.write(response.content)
                    size = f.tell()
                    progress = DownloadProgress(self._url, size, self.report_progress)
                    progress.end()
                else:
                    # requests return headers as strings, so convert total_length to int
                    progress = DownloadProgress(self._url, int(total_length), self.report_progress)
                    bytes_read = 0
                    for buf in response.iter_content(1024 * 1024):
                        if buf:
                            f.write(buf)
                            f.flush()
                            bytes_read += len(buf)
                            progress.update(bytes_read)
                    progress.end()
                log.info("Image download finished")
        except RequestException as e:
            error = "Error downloading liveimg: {}".format(e)
            log.error(error)
            raise SourceSetupError(error) from e
        else:
            if not os.path.exists(image_path):
                error = "Failed to download {}, file doesn't exist".format(self._url)
                log.error(error)
                raise SourceSetupError(error)

    def _check_image_sum(self, image_path, checksum):
        self.report_progress("Checking image checksum")
        sha256 = hashlib.sha256()
        with open(image_path, "rb") as f:
            while True:
                data = f.read(1024 * 1024)
                if not data:
                    break
                sha256.update(data)
        filesum = sha256.hexdigest()
        log.debug("sha256 of %s is %s", image_path, filesum)

        if lowerASCII(checksum) != filesum:
            log.error("%s does not match checksum of %s.", checksum, image_path)
            raise SourceSetupError("Checksum of image {} does not match".format(image_path))

    def _mount_image(self, image_path, mount_point):
        # Work around inability to move shared filesystems.
        # Also, do not share the image mounts with /run bind-mounted to physical
        # target root during storage.mount_filesystems.
        rc = execWithRedirect("mount", ["--make-rprivate", "/"])
        if rc != 0:
            log.error("mount error (%s) making mount of '/' rprivate", rc)
            raise SourceSetupError("Mount error {}".format(rc))

        # Mount the image and check to see if it is a LiveOS/*.img
        # style squashfs image. If so, move it to IMAGE_DIR and mount the real
        # root image on mount_point
        rc = mount(image_path, mount_point, fstype="auto", options="ro")
        if rc != 0:
            log.error("mount error (%s) with %s", rc, image_path)
            raise SourceSetupError("Mount error {}".format(rc))

        nested_image_files = glob.glob(mount_point + "/LiveOS/*.img")
        if nested_image_files:
            # Mount the first .img in the directory on mount_point
            nested_image = sorted(nested_image_files)[0]

            # move the mount to IMAGE_DIR
            os.makedirs(IMAGE_DIR, 0o755)
            rc = execWithRedirect("mount", ["--move", mount_point, IMAGE_DIR])
            if rc != 0:
                log.error("error %s moving mount", rc)
                raise SourceSetupError("Mount error {}".format(rc))

            nested_image_path = IMAGE_DIR + "/LiveOS/" + os.path.basename(nested_image)
            rc = mount(nested_image_path, mount_point, fstype="auto", options="ro")
            if rc != 0:
                log.error("mount error (%s) with %s", rc, nested_image_path)
                raise SourceSetupError("Mount error {} with {}".format(rc, nested_image_path))

        # FIXME: Update kernel version outside of this task
        #
        # Grab the kernel version list now so it's available after umount
        # self._update_kernel_version_list()

        # FIXME: This should be done by the module
        # # source = os.statvfs(mount_point)
        # self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)

    def run(self):
        """Run set up or installation source."""
        image_path_from_url = get_local_image_path_from_url(self._url)
        if image_path_from_url:
            self._image_path = image_path_from_url
        else:
            self._download_image(self._url, self._image_path, self._session)

        # TODO - do we use it at all in LiveImage
        # Used to make install progress % look correct
        # self._adj_size = os.stat(self.image_path).st_size

        if self._checksum:
            self._check_image_sum(self._image_path, self._checksum)

        if not url_target_is_tarfile(self._url):
            self._mount_image(self._image_path, self._image_mount_point)

        log.debug("Source image file path: %s", self._image_path)
        return self._image_path


class TeardownInstallationSourceImageTask(Task):
    """Task to tear down installation source image."""

    def __init__(self, image_path, url, image_mount_point):
        """Create a new task.

        :param image_path: destination path for image download
        :type image_path: str
        :param url: installation source image url
        :type url: str
        :param image_mount_point: Mount point of the source image
        :type image_mount_point: str
        """
        super().__init__()
        self._image_path = image_path
        self._url = url
        self._image_mount_point = image_mount_point

    @property
    def name(self):
        return "Tear down installation source image."""

    def run(self):
        """Run tear down of installation source image."""
        if not url_target_is_tarfile(self._url):
            unmount(self._image_mount_point, raise_exc=True)
            # FIXME: Payload and LiveOS stuff
            # FIXME: do we need a task for this?
            if os.path.exists(IMAGE_DIR + "/LiveOS"):
                # FIXME: catch and pass the exception
                unmount(IMAGE_DIR, raise_exc=True)
                os.rmdir(IMAGE_DIR)

        if not get_local_image_path_from_url(self._url):
            if os.path.exists(self._image_path):
                os.unlink(self._image_path)


class DownloadProgress(object):
    """Provide methods for download progress reporting."""

    def __init__(self, url, size, report_callback):
        """Create a progress object for given task.

        :param url: url of the download
        :type url: str
        :param size: length of the file
        :type size: int
        :param report_callback: callback with progress message argument
        :type report_callback: callable taking str argument
        """
        self.report = report_callback
        self.url = url
        self.size = size
        self._pct = -1

    def update(self, bytes_read):
        """Download update.

        :param bytes_read: Bytes read so far
        :type bytes_read:  int
        """
        if not bytes_read:
            return
        pct = min(100, int(100 * bytes_read / self.size))

        if pct == self._pct:
            return
        self._pct = pct
        self.report("Downloading image %(url)s (%(pct)d%%)" %
                    {"url": self.url, "pct": pct})

    def end(self):
        """Download complete."""
        self.report("Downloading image %(url)s (%(pct)d%%)" %
                    {"url": self.url, "pct": 100})
