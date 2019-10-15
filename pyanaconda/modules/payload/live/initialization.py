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
import glob

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payload.live.utils import get_local_image_path_from_url, \
    url_target_is_tarfile
from pyanaconda.payload.utils import unmount
from pyanaconda.core.constants import IMAGE_DIR

from pyanaconda.core.util import execWithRedirect

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DownloadProgress(object):
    """Provide methods for download progress reporting."""

    def __init__(self, url, size, report_callback):
        """Create a progress object for given task.

        :param url: url of the download
        :type url: str
        :param size: length of the file
        :type size: int
        :param report_callback: callback with progress message argument
        :type task: callable taking str argument
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
            #FIXME: Payload and LiveOS stuff
            # FIXME: do we need a task for this?
            if os.path.exists(IMAGE_DIR + "/LiveOS"):
                # FIXME: catch and pass the exception
                unmount(IMAGE_DIR, raise_exc=True)
                os.rmdir(IMAGE_DIR)

        if not get_local_image_path_from_url(self._url):
            if os.path.exists(self._image_path):
                os.unlink(self._image_path)


class UpdateBLSConfigurationTask(Task):
    """Task to update BLS configuration."""

    def __init__(self, sysroot, kernel_version_list):
        """Create a new task.

        :param sysroot: a path to the root of the installed system
        :type sysroot: str
        :param kernel_version_list: list of kernel versions for updating of BLS configuration
        :type krenel_version_list: list(str)
        """
        super().__init__()
        self._sysroot = sysroot
        self._kernel_version_list = kernel_version_list

    @property
    def name(self):
        return "Update BLS configuration."""

    def run(self):
        """Run update of bls configuration."""
        # Not using BLS configuration, skip it
        if os.path.exists(self._sysroot + "/usr/sbin/new-kernel-pkg"):
            return

        # TODO: test if this is not a dir install

        # Remove any existing BLS entries, they will not match the new system's
        # machine-id or /boot mountpoint.
        for file in glob.glob(self._sysroot + "/boot/loader/entries/*.conf"):
            log.info("Removing old BLS entry: %s", file)
            os.unlink(file)

        # Create new BLS entries for this system
        for kernel in self._kernel_version_list:
            log.info("Regenerating BLS info for %s", kernel)
            execWithRedirect(
                "kernel-install",
                ["add", kernel, "/lib/modules/{0}/vmlinuz".format(kernel)],
                root=self._sysroot
            )
