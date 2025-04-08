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
import glob
import hashlib
import os
import stat
from threading import Lock

import requests
from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_IMAGE, TAR_SUFFIX, \
    NETWORK_CONNECTION_TIMEOUT, INSTALL_TREE, IMAGE_DIR, THREAD_LIVE_PROGRESS
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.modules.payloads.payload.live_image.utils import get_kernel_version_list_from_tar
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadInstallError, PayloadSetupError
from pyanaconda.payload.live.download_progress import DownloadProgress
from pyanaconda.payload.live.payload_base import BaseLivePayload
from pyanaconda.progress import progressQ
from pyanaconda.threading import threadMgr, AnacondaThread

log = get_packaging_logger()

__all__ = ["LiveImagePayload"]


class LiveImagePayload(BaseLivePayload):
    """ Install using a live filesystem image from the network """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_size = 0
        self._proxies = {}
        self._session = util.requests_session()
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

    @property
    def is_tarfile(self):
        """ Return True if the url ends with a tar suffix """
        return any(self.data.liveimg.url.endswith(suffix) for suffix in TAR_SUFFIX)

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
            ssl_verify = not self.data.liveimg.noverifyssl
            response = self._session.head(
                self.data.liveimg.url,
                proxies=self._proxies,
                verify=ssl_verify,
                timeout=NETWORK_CONNECTION_TIMEOUT
            )

            # At this point we know we can get the image and what its size is
            # Make a guess as to minimum size needed:
            # Enough space for image and image * 3
            if response.headers.get('content-length'):
                self._min_size = int(response.headers.get('content-length')) * 4
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

        # Used to make install progress % look correct
        self._adj_size = os.stat(self.image_path)[stat.ST_SIZE]

        if self.data.liveimg.checksum:
            progressQ.send_message(_("Checking image checksum"))
            sha256 = hashlib.sha256()
            with open(self.image_path, "rb") as f:
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    sha256.update(data)
            filesum = sha256.hexdigest()
            log.debug("sha256 of %s is %s", self.data.liveimg.url, filesum)

            if util.lowerASCII(self.data.liveimg.checksum) != filesum:
                log.error("%s does not match checksum.", self.data.liveimg.checksum)
                raise PayloadInstallError("Checksum of image does not match")

        # If this looks like a tarfile, skip trying to mount it
        if self.is_tarfile:
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
            self._update_kernel_version_list()
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

            self._update_kernel_version_list()

            source = os.statvfs(INSTALL_TREE)
            self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)

    def install(self):
        """ Install the payload if it is a tar.
            Otherwise fall back to rsync of INSTALL_TREE
        """
        # If it doesn't look like a tarfile use the super's install()
        if not self.is_tarfile:
            super().install()
            return

        # Use 2x the archive's size to estimate the size of the install
        # This is used to drive the progress display
        self.source_size = os.stat(self.image_path)[stat.ST_SIZE] * 2

        self.pct_lock = Lock()
        self.pct = 0
        threadMgr.add(AnacondaThread(name=THREAD_LIVE_PROGRESS,
                                     target=self.progress))

        cmd = "tar"
        # preserve: ACL's, xattrs, and SELinux context
        args = ["--numeric-owner", "--selinux", "--acls", "--xattrs", "--xattrs-include", "*",
                "--exclude", "./dev/*", "--exclude", "./proc/*", "--exclude", "./tmp/*",
                "--exclude", "./sys/*", "--exclude", "./run/*", "--exclude", "./boot/*rescue*",
                "--exclude", "./boot/loader", "--exclude", "./boot/efi/loader",
                "--exclude", "./etc/machine-id", "--exclude", "./etc/machine-info",
                "-xaf", self.image_path, "-C", conf.target.system_root]
        try:
            rc = util.execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = None
            err = str(e)
            log.error(err)
        else:
            err = None
            msg = "%s exited with code %d" % (cmd, rc)
            log.info(msg)

        if err:
            raise PayloadInstallError(err or msg)

        # Wait for progress thread to finish
        with self.pct_lock:
            self.pct = 100
        threadMgr.wait(THREAD_LIVE_PROGRESS)

    def post_install(self):
        """ Unmount and remove image

            If file:// was used, just unmount it.
        """
        super().post_install()

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
        # If it doesn't look like a tarfile use the super's kernel_version_list
        if not self.is_tarfile:
            return super().kernel_version_list

        if self._kernel_version_list:
            return self._kernel_version_list

        # Cache a list of the kernels (the tar payload may be cleaned up on subsequent calls)
        if not os.path.exists(self.image_path):
            raise PayloadInstallError("kernel_version_list: missing tar payload")

        self._kernel_version_list = get_kernel_version_list_from_tar(self.image_path)

        return self._kernel_version_list
