# Live media software payload management.
#
# Copyright (C) 2019  Red Hat, Inc.
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

"""
    TODO
        - error handling!!!
        - document all methods
        - LiveImagePayload
            - register the live image, either via self.data.method or in setup
              using storage

"""
import os
import stat
import requests
import hashlib
import glob
import functools
from time import sleep
from threading import Lock

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.core import util
from pyanaconda.core.i18n import _
from pyanaconda.payload import Payload
from pyanaconda.payload import payload_utils
from pyanaconda.payload.errors import PayloadSetupError, PayloadInstallError
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.progress import progressQ

from pyanaconda.core.constants import INSTALL_TREE, THREAD_LIVE_PROGRESS
from pyanaconda.core.constants import IMAGE_DIR, TAR_SUFFIX

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_packaging_logger
log = get_packaging_logger()


class LiveImagePayload(Payload):
    """ A LivePayload copies the source image onto the target system. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Used to adjust size of sysroot when files are already present
        self._adj_size = 0
        self.pct = 0
        self.pct_lock = None
        self.source_size = 1

        self._kernel_version_list = []

    def setup(self, storage):
        super().setup(storage)

        # Mount the live device and copy from it instead of the overlay at /
        osimg = storage.devicetree.get_device_by_path(self.data.method.partition)
        if not osimg:
            raise PayloadInstallError("Unable to find osimg for %s" % self.data.method.partition)

        if not stat.S_ISBLK(os.stat(osimg.path)[stat.ST_MODE]):
            exn = PayloadSetupError("%s is not a valid block device" %
                                    (self.data.method.partition,))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        rc = payload_utils.mount(osimg.path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            raise PayloadInstallError("Failed to mount the install tree")

        # Grab the kernel version list now so it's available after umount
        self._update_kernel_version_list()

        source = os.statvfs(INSTALL_TREE)
        self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)

    def unsetup(self):
        super().unsetup()

        # Unmount a previously mounted live tree
        payload_utils.unmount(INSTALL_TREE)

    def pre_install(self):
        """ Perform pre-installation tasks. """
        super().pre_install()
        progressQ.send_message(_("Installing software") + (" %d%%") % (0,))

    def progress(self):
        """Monitor the amount of disk space used on the target and source and
           update the hub's progress bar.
        """
        mountpoints = self.storage.mountpoints.copy()
        last_pct = -1
        while self.pct < 100:
            dest_size = 0
            for mnt in mountpoints:
                mnt_stat = os.statvfs(util.getSysroot() + mnt)
                dest_size += mnt_stat.f_frsize * (mnt_stat.f_blocks - mnt_stat.f_bfree)
            if dest_size >= self._adj_size:
                dest_size -= self._adj_size

            pct = int(100 * dest_size / self.source_size)
            if pct != last_pct:
                with self.pct_lock:
                    self.pct = pct
                last_pct = pct
                progressQ.send_message(_("Installing software") + (" %d%%") %
                                       (min(100, self.pct),))
            sleep(0.777)

    def install(self):
        """ Install the payload. """

        if self.source_size <= 0:
            raise PayloadInstallError("Nothing to install")

        self.pct_lock = Lock()
        self.pct = 0
        threadMgr.add(AnacondaThread(name=THREAD_LIVE_PROGRESS,
                                     target=self.progress))

        cmd = "rsync"
        # preserve: permissions, owners, groups, ACL's, xattrs, times,
        #           symlinks, hardlinks
        # go recursively, include devices and special files, don't cross
        # file system boundaries
        args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/boot/loader/", "--exclude", "/boot/efi/loader/",
                "--exclude", "/etc/machine-id", INSTALL_TREE + "/", util.getSysroot()]
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

        if err or rc == 11:
            exn = PayloadInstallError(err or msg)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Wait for progress thread to finish
        with self.pct_lock:
            self.pct = 100
        threadMgr.wait(THREAD_LIVE_PROGRESS)

        # Live needs to create the rescue image before bootloader is written
        if os.path.exists(util.getSysroot() + "/usr/sbin/new-kernel-pkg"):
            use_nkp = True
        else:
            log.warning("new-kernel-pkg does not exist - grubby wasn't installed?")
            use_nkp = False

        for kernel in self.kernel_version_list:
            log.info("Generating rescue image for %s", kernel)
            if use_nkp:
                util.execInSysroot("new-kernel-pkg",
                                   ["--rpmposttrans", kernel])
            else:
                files = glob.glob(util.getSysroot() + "/etc/kernel/postinst.d/*")
                srlen = len(util.getSysroot())
                files = sorted([f[srlen:] for f in files
                                if os.access(f, os.X_OK)])
                for file in files:
                    util.execInSysroot(file,
                                       [kernel, "/boot/vmlinuz-%s" % kernel])

    def post_install(self):
        """ Perform post-installation tasks. """
        progressQ.send_message(_("Performing post-installation setup tasks"))
        payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        super().post_install()

        # Make sure the new system has a machine-id, it won't boot without it
        # (and nor will some of the subsequent commands)
        if not os.path.exists(util.getSysroot() + "/etc/machine-id"):
            log.info("Generating machine ID")
            util.execInSysroot("systemd-machine-id-setup", [])

        for kernel in self.kernel_version_list:
            if not os.path.exists(util.getSysroot() + "/usr/sbin/new-kernel-pkg"):
                log.info("Regenerating BLS info for %s", kernel)
                util.execInSysroot("kernel-install", ["add",
                                                      kernel,
                                                      "/lib/modules/{0}/vmlinuz".format(kernel)])

    @property
    def space_required(self):
        return Size(util.getDirSize("/") * 1024)

    def _update_kernel_version_list(self):
        files = glob.glob(INSTALL_TREE + "/boot/vmlinuz-*")
        files.extend(glob.glob(INSTALL_TREE + "/boot/efi/EFI/%s/vmlinuz-*" %
                               conf.bootloader.efi_dir))

        self._kernel_version_list = sorted((f.split("/")[-1][8:] for f in files
                                           if os.path.isfile(f) and "-rescue-" not in f),
                                           key=functools.cmp_to_key(payload_utils.version_cmp))

    @property
    def kernel_version_list(self):
        return self._kernel_version_list


class DownloadProgress(object):
    """ Provide methods for download progress reporting."""

    def start(self, url, size):
        """ Start of download

            :param url:      url of the download
            :type url:       str
            :param size:     length of the file
            :type size:      int
        """
        self.url = url
        self.size = size
        self._pct = -1

    def update(self, bytes_read):
        """ Download update

            :param bytes_read: Bytes read so far
            :type bytes_read:  int
        """
        if not bytes_read:
            return
        pct = min(100, int(100 * bytes_read / self.size))

        if pct == self._pct:
            return
        self._pct = pct
        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") %
                               {"url": self.url, "pct": pct})

    def end(self, bytes_read):
        """ Download complete

            :param bytes_read: Bytes read so far
            :type bytes_read:  int
        """
        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") %
                               {"url": self.url, "pct": 100})


class LiveImageKSPayload(LiveImagePayload):
    """ Install using a live filesystem image from the network """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_size = 0
        self._proxies = {}
        self.image_path = util.getSysroot() + "/disk.img"

    @property
    def is_tarfile(self):
        """ Return True if the url ends with a tar suffix """
        return any(self.data.method.url.endswith(suffix) for suffix in TAR_SUFFIX)

    def _setup_url_image(self):
        """ Check to make sure the url is available and estimate the space
            needed to download and install it.
        """
        self._proxies = {}
        if self.data.method.proxy:
            try:
                proxy = ProxyString(self.data.method.proxy)
                self._proxies = {"http": proxy.url,
                                 "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for liveimg --proxy=\"%s\": %s",
                         self.data.method.proxy, e)

        error = None
        try:
            response = self._session.get(self.data.method.url, proxies=self._proxies, verify=True)

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
        if not os.path.exists(self.data.method.url[7:]):
            return "file does not exist: %s" % self.data.method.url

        self._min_size = os.stat(self.data.method.url[7:])[stat.ST_SIZE] * 3
        return None

    def setup(self, storage):
        """ Check the availability and size of the image.
        """
        # This is on purpose, we don't want to call LiveImagePayload's setup method.
        # FIXME: this should be solved on a inheritance level not like this
        Payload.setup(self, storage)

        if self.data.method.url.startswith("file://"):
            error = self._setup_file_image()
        else:
            error = self._setup_url_image()

        if error:
            exn = PayloadInstallError(str(error))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        log.debug("liveimg size is %s", self._min_size)

    def unsetup(self):
        # Skip LiveImagePayload's unsetup method
        # FIXME: this should be solved on a inheritance level not like this
        Payload.unsetup(self)

    def _pre_install_url_image(self):
        """ Download the image using Requests with progress reporting"""

        error = None
        progress = DownloadProgress()
        try:
            log.info("Starting image download")
            with open(self.image_path, "wb") as f:
                ssl_verify = not self.data.method.noverifyssl
                response = self._session.get(self.data.method.url, proxies=self._proxies,
                                             verify=ssl_verify, stream=True)
                total_length = response.headers.get('content-length')
                if total_length is None:  # no content length header
                    # just download the file in one go and fake the progress reporting once done
                    log.warning("content-length header is missing for the installation image, "
                                "download progress reporting will not be available")
                    f.write(response.content)
                    size = f.tell()
                    progress.start(self.data.method.url, size)
                    progress.end(size)
                else:
                    # requests return headers as strings, so convert total_length to int
                    progress.start(self.data.method.url, int(total_length))
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
                error = "Failed to download %s, file doesn't exist" % self.data.method.url
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
        if self.data.method.url.startswith("file://"):
            self.image_path = self.data.method.url[7:]
        else:
            error = self._pre_install_url_image()

        if error:
            exn = PayloadInstallError(str(error))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Used to make install progress % look correct
        self._adj_size = os.stat(self.image_path)[stat.ST_SIZE]

        if self.data.method.checksum:
            progressQ.send_message(_("Checking image checksum"))
            sha256 = hashlib.sha256()
            with open(self.image_path, "rb") as f:
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    sha256.update(data)
            filesum = sha256.hexdigest()
            log.debug("sha256 of %s is %s", self.data.method.url, filesum)

            if util.lowerASCII(self.data.method.checksum) != filesum:
                log.error("%s does not match checksum.", self.data.method.checksum)
                exn = PayloadInstallError("Checksum of image does not match")
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

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
            exn = PayloadInstallError("mount error %s" % rc)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Mount the image and check to see if it is a LiveOS/*.img
        # style squashfs image. If so, move it to IMAGE_DIR and mount the real
        # root image on INSTALL_TREE
        rc = payload_utils.mount(self.image_path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            log.error("mount error (%s) with %s", rc, self.image_path)
            exn = PayloadInstallError("mount error %s" % rc)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

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
                exn = PayloadInstallError("mount error %s" % rc)
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

            img_file = IMAGE_DIR+"/LiveOS/" + os.path.basename(sorted(img_files)[0])
            rc = payload_utils.mount(img_file, INSTALL_TREE, fstype="auto", options="ro")
            if rc != 0:
                log.error("mount error (%s) with %s", rc, img_file)
                exn = PayloadInstallError("mount error %s with %s" % (rc, img_file))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

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
        args = ["--selinux", "--acls", "--xattrs", "--xattrs-include", "*",
                "--exclude", "/dev/", "--exclude", "/proc/",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/etc/machine-id", "-xaf", self.image_path, "-C", util.getSysroot()]
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
            exn = PayloadInstallError(err or msg)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Wait for progress thread to finish
        with self.pct_lock:
            self.pct = 100
        threadMgr.wait(THREAD_LIVE_PROGRESS)

        # Live needs to create the rescue image before bootloader is written
        for kernel in self.kernel_version_list:
            log.info("Generating rescue image for %s", kernel)
            util.execInSysroot("new-kernel-pkg",
                               ["--rpmposttrans", kernel])

    def post_install(self):
        """ Unmount and remove image

            If file:// was used, just unmount it.
        """
        super().post_install()

        if os.path.exists(IMAGE_DIR + "/LiveOS"):
            payload_utils.unmount(IMAGE_DIR, raise_exc=True)

        if os.path.exists(self.image_path) and not self.data.method.url.startswith("file://"):
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

        import tarfile
        with tarfile.open(self.image_path) as archive:
            names = archive.getnames()

            # Strip out vmlinuz- from the names
            return sorted((n.split("/")[-1][8:] for n in names if "boot/vmlinuz-" in n),
                          key=functools.cmp_to_key(payload_utils.version_cmp))
