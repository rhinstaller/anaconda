# livepayload.py
# Live media software payload management.
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
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
from time import sleep
from threading import Lock
from urlgrabber.grabber import URLGrabber
from urlgrabber.grabber import URLGrabError
from pyanaconda.iutil import ProxyString, ProxyStringError, lowerASCII
import urllib
import hashlib
import glob

from pyanaconda.packaging import ImagePayload, PayloadSetupError, PayloadInstallError

from pyanaconda.constants import INSTALL_TREE, THREAD_LIVE_PROGRESS
from pyanaconda.constants import IMAGE_DIR, TAR_SUFFIX

from pyanaconda import iutil

import logging
log = logging.getLogger("packaging")

from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.progress import progressQ
from blivet.size import Size
import blivet.util
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.i18n import _
from pyanaconda.packaging import versionCmp

class LiveImagePayload(ImagePayload):
    """ A LivePayload copies the source image onto the target system. """
    def __init__(self, *args, **kwargs):
        super(LiveImagePayload, self).__init__(*args, **kwargs)
        # Used to adjust size of sysroot when files are already present
        self._adj_size = 0
        self.pct = 0
        self.pct_lock = None
        self.source_size = 1

        self._kernelVersionList = []

    def setup(self, storage, instClass):
        super(LiveImagePayload, self).setup(storage, instClass)

        # Mount the live device and copy from it instead of the overlay at /
        osimg = storage.devicetree.getDeviceByPath(self.data.method.partition)
        if not stat.S_ISBLK(os.stat(osimg.path)[stat.ST_MODE]):
            exn = PayloadSetupError("%s is not a valid block device" % (self.data.method.partition,))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        rc = blivet.util.mount(osimg.path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            raise PayloadInstallError("Failed to mount the install tree")

        # Grab the kernel version list now so it's available after umount
        self._updateKernelVersionList()

        source = iutil.eintr_retry_call(os.statvfs, INSTALL_TREE)
        self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)

    def unsetup(self):
        super(LiveImagePayload, self).unsetup()

        # Unmount a previously mounted live tree
        try:
            blivet.util.umount(INSTALL_TREE)
        except OSError:
            pass

    def preInstall(self, packages=None, groups=None):
        """ Perform pre-installation tasks. """
        super(LiveImagePayload, self).preInstall(packages=packages, groups=groups)
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
                mnt_stat = iutil.eintr_retry_call(os.statvfs, iutil.getSysroot()+mnt)
                dest_size += mnt_stat.f_frsize * (mnt_stat.f_blocks - mnt_stat.f_bfree)
            if dest_size >= self._adj_size:
                dest_size -= self._adj_size

            pct = int(100 * dest_size / self.source_size)
            if pct != last_pct:
                with self.pct_lock:
                    self.pct = pct
                last_pct = pct
                progressQ.send_message(_("Installing software") + (" %d%%") % (min(100, self.pct),))
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
                "--exclude", "/etc/machine-id", INSTALL_TREE+"/", iutil.getSysroot()]
        try:
            rc = iutil.execWithRedirect(cmd, args)
        except (OSError, RuntimeError) as e:
            msg = None
            err = str(e)
            log.error(err)
        else:
            err = None
            msg = "%s exited with code %d" % (cmd, rc)
            log.info(msg)

        if err or rc == 12:
            exn = PayloadInstallError(err or msg)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Wait for progress thread to finish
        with self.pct_lock:
            self.pct = 100
        threadMgr.wait(THREAD_LIVE_PROGRESS)

        # Live needs to create the rescue image before bootloader is written
        for kernel in self.kernelVersionList:
            log.info("Generating rescue image for %s", kernel)
            iutil.execInSysroot("new-kernel-pkg",
                                ["--rpmposttrans", kernel])

    def postInstall(self):
        """ Perform post-installation tasks. """
        progressQ.send_message(_("Performing post-installation setup tasks"))
        blivet.util.umount(INSTALL_TREE)

        super(LiveImagePayload, self).postInstall()

        # Make sure the new system has a machine-id, it won't boot without it
        if not os.path.exists(iutil.getSysroot()+"/etc/machine-id"):
            iutil.execInSysroot("systemd-machine-id-setup", [])

    @property
    def spaceRequired(self):
        return Size(iutil.getDirSize("/")*1024)

    def _updateKernelVersionList(self):
        files = glob.glob(INSTALL_TREE + "/boot/vmlinuz-*")
        files.extend(glob.glob(INSTALL_TREE + "/boot/efi/EFI/%s/vmlinuz-*" % self.instclass.efi_dir))

        self._kernelVersionList = sorted((f.split("/")[-1][8:] for f in files
           if os.path.isfile(f) and "-rescue-" not in f), cmp=versionCmp)

    @property
    def kernelVersionList(self):
        return self._kernelVersionList

class URLGrabberProgress(object):
    """ Provide methods for urlgrabber progress."""
    def start(self, filename, url, basename, size, text):
        """ Start of urlgrabber download

            :param filename: path and file that download will be saved to
            :type filename:  string
            :param url:      url to download from
            :type url:       string
            :param basename: file that it will be saved to
            :type basename:  string
            :param size:     length of the file
            :type size:      int
            :param text:     unknown
            :type text:      unknown
        """
        self.filename = filename
        self.url = url
        self.basename = basename
        self.size = size
        self.text = text
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

        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") % \
                {"url" : self.url, "pct" : pct})

    def end(self, bytes_read):
        """ Download complete

            :param bytes_read: Bytes read so far
            :type bytes_read:  int
        """
        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") % \
                {"url" : self.url, "pct" : 100})

class LiveImageKSPayload(LiveImagePayload):
    """ Install using a live filesystem image from the network """
    def __init__(self, *args, **kwargs):
        super(LiveImageKSPayload, self).__init__(*args, **kwargs)
        self._min_size = 0
        self._proxies = {}
        self.image_path = iutil.getSysroot()+"/disk.img"

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
            req = urllib.urlopen(self.data.method.url, proxies=self._proxies)

            # At this point we know we can get the image and what its size is
            # Make a guess as to minimum size needed:
            # Enough space for image and image * 3
            if req.info().get("content-length"):
                self._min_size = int(req.info().get('content-length')) * 4
        except IOError as e:
            log.error("Error opening liveimg: %s", e)
            error = e
        else:
            # If it is a http request we need to check the code
            method = self.data.method.url.split(":", 1)[0]
            if method.startswith("http") and req.getcode() != 200:
                error = "http request returned %s" % req.getcode()

        return error

    def _setup_file_image(self):
        """ Check to make sure the file is available and estimate the space
            needed to install it.
        """
        if not os.path.exists(self.data.method.url[7:]):
            return "file does not exist: %s" % self.data.method.url

        self._min_size = os.stat(self.data.method.url[7:])[stat.ST_SIZE] * 3
        return None

    def setup(self, storage, instClass):
        """ Check the availability and size of the image.
        """
        # This is on purpose, we don't want to call LiveImagePayload's setup method.
        ImagePayload.setup(self, storage, instClass)

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
        ImagePayload.unsetup(self)

    def _preInstall_url_image(self):
        """ Download the image using urlgrabber """
        # Setup urlgrabber and call back to download image to sysroot
        progress = URLGrabberProgress()
        ugopts = {"ssl_verify_peer": not self.data.method.noverifyssl,
                  "ssl_verify_host": not self.data.method.noverifyssl,
                  "proxies" : self._proxies,
                  "progress_obj" : progress,
                  "copy_local" : True}

        error = None
        try:
            ug = URLGrabber()
            ug.urlgrab(self.data.method.url, self.image_path, **ugopts)
        except URLGrabError as e:
            log.error("Error downloading liveimg: %s", e)
            error = e
        else:
            if not os.path.exists(self.image_path):
                error = "Failed to download %s, file doesn't exist" % self.data.method.url
                log.error(error)

    def preInstall(self, *args, **kwargs):
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
            error = self._preInstall_url_image()

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
                    data = f.read(1024*1024)
                    if not data:
                        break
                    sha256.update(data)
            filesum = sha256.hexdigest()
            log.debug("sha256 of %s is %s", self.data.method.url, filesum)

            if lowerASCII(self.data.method.checksum) != filesum:
                log.error("%s does not match checksum.", self.data.method.checksum)
                exn = PayloadInstallError("Checksum of image does not match")
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

        # If this looks like a tarfile, skip trying to mount it
        if self.is_tarfile:
            return

        # Mount the image and check to see if it is a LiveOS/*.img
        # style squashfs image. If so, move it to IMAGE_DIR and mount the real
        # root image on INSTALL_TREE
        rc = blivet.util.mount(self.image_path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            log.error("mount error (%s) with %s", rc, self.image_path)
            exn = PayloadInstallError("mount error %s" % rc)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        # Nothing more to mount
        if not os.path.exists(INSTALL_TREE+"/LiveOS"):
            self._updateKernelVersionList()
            return

        # Mount the first .img in the directory on INSTALL_TREE
        img_files = glob.glob(INSTALL_TREE+"/LiveOS/*.img")
        if img_files:
            # move the mount to IMAGE_DIR
            os.makedirs(IMAGE_DIR, 0o755)
            # work around inability to move shared filesystems
            rc = iutil.execWithRedirect("mount",
                                        ["--make-rprivate", "/"])
            if rc == 0:
                rc = iutil.execWithRedirect("mount",
                                            ["--move", INSTALL_TREE, IMAGE_DIR])
            if rc != 0:
                log.error("error %s moving mount", rc)
                exn = PayloadInstallError("mount error %s" % rc)
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

            img_file = IMAGE_DIR+"/LiveOS/"+os.path.basename(sorted(img_files)[0])
            rc = blivet.util.mount(img_file, INSTALL_TREE, fstype="auto", options="ro")
            if rc != 0:
                log.error("mount error (%s) with %s", rc, img_file)
                exn = PayloadInstallError("mount error %s with %s" % (rc, img_file))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

            self._updateKernelVersionList()

            source = iutil.eintr_retry_call(os.statvfs, INSTALL_TREE)
            self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)

    def install(self):
        """ Install the payload if it is a tar.
            Otherwise fall back to rsync of INSTALL_TREE
        """
        # If it doesn't look like a tarfile use the super's install()
        if not self.is_tarfile:
            super(LiveImageKSPayload, self).install()
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
        args = ["--selinux", "--acls", "--xattrs",
                "--exclude", "/dev/", "--exclude", "/proc/",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/etc/machine-id", "-xaf", self.image_path, "-C", iutil.getSysroot()]
        try:
            rc = iutil.execWithRedirect(cmd, args)
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
        for kernel in self.kernelVersionList:
            log.info("Generating rescue image for %s", kernel)
            iutil.execInSysroot("new-kernel-pkg",
                                ["--rpmposttrans", kernel])

    def postInstall(self):
        """ Unmount and remove image

            If file:// was used, just unmount it.
        """
        super(LiveImageKSPayload, self).postInstall()

        if os.path.exists(IMAGE_DIR+"/LiveOS"):
            blivet.util.umount(IMAGE_DIR)

        if os.path.exists(self.image_path) and not self.data.method.url.startswith("file://"):
            os.unlink(self.image_path)

    @property
    def spaceRequired(self):
        """ We don't know the filesystem size until it is downloaded.

            Default to 1G which should be enough for a minimal image download
            and install.
        """
        if self._min_size:
            return Size(self._min_size)
        else:
            return Size(1024*1024*1024)

    @property
    def kernelVersionList(self):
        # If it doesn't look like a tarfile use the super's kernelVersionList
        if not self.is_tarfile:
            return super(LiveImageKSPayload, self).kernelVersionList

        import tarfile
        with tarfile.open(self.image_path) as archive:
            names = archive.getnames()

            # Strip out vmlinuz- from the names
            return sorted((n.split("/")[-1][8:] for n in names if "boot/vmlinuz-" in n),
                    cmp=versionCmp)
