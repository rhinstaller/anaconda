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
import re
import stat

from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_OS, INSTALL_TREE, \
    SOURCE_TYPE_LIVE_OS_IMAGE, THREAD_LIVE_PROGRESS
from pyanaconda.core.i18n import _
from pyanaconda.core.util import execInSysroot, execWithCapture, execWithRedirect
from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadInstallError, PayloadSetupError
from pyanaconda.payload.live.payload_base import BaseLivePayload
from pyanaconda.progress import progressQ
from pyanaconda.threading import threadMgr, AnacondaThread

log = get_packaging_logger()

__all__ = ["LiveOSPayload"]


class LiveOSPayload(BaseLivePayload):
    """ A LivePayload copies the source image onto the target system. """

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_LIVE_OS

    @staticmethod
    def _get_live_os_image():
        """Detect live os image on the system.

        FIXME: This is a temporary workaround.

        :return: a path to the image
        """
        payloads_proxy = PAYLOADS.get_proxy()
        source_path = payloads_proxy.CreateSource(SOURCE_TYPE_LIVE_OS_IMAGE)

        source_proxy = PAYLOADS.get_proxy(source_path)
        return source_proxy.DetectLiveOSImage()

    def get_number_of_inodes(self):
        """ Examine the contents of the filename to determine whether it's a plain squashfs.
        " If the return value is True, then the image is considered plain. This means
        " it does not contain any embedded filesystem inside. If the value returned is False,
        " it means that the filesystem has an embedded, in Fedora -- ext4, filesystem inside
        " a squashfs image.
        " :param: self.osimg_path -- a path to the target file or a block device
        " :returns: bool
        """
        search_string = r"Number of inodes (\d+)"
        file_squashfs_information = execWithCapture("unsquashfs", ["-s", self.osimg_path])
        match_obj = re.search(search_string, file_squashfs_information)
        try:
            number_of_inodes = int(match_obj.group(1))
        except AttributeError as e:
            log.debug("The filesystem is either non-plain or an error has occured")
            debug_message = str(e)
            log.debug(debug_message)
            return -1
        return number_of_inodes

    def setup(self):
        super().setup()
        # Mount the live device and copy from it instead of the overlay at /
        osimg_spec = self._get_live_os_image()

        if not osimg_spec:
            raise PayloadSetupError("No live image found!")

        osimg = payload_utils.resolve_device(osimg_spec)
        if not osimg:
            raise PayloadInstallError("Unable to find osimg for {}".format(osimg_spec))

        osimg_path = payload_utils.get_device_path(osimg)
        if not stat.S_ISBLK(os.stat(osimg_path)[stat.ST_MODE]):
            exn = PayloadSetupError("{} is not a valid block device".format(osimg_spec))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        rc = payload_utils.mount(osimg_path, INSTALL_TREE, fstype="auto", options="ro")
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

    def install(self):
        # Define a number of files from which a filesystem is considered plain
        plain_squashfs_threshold = 50
        if self.get_number_of_inodes() < plain_squashfs_threshold:
            # Proceed with the standard installation.
            super().install()
            return
        # Use an optimization in case the SQUASHFS image is plain.
        # Include only the directories from the squashfs as specified below.

        cmd = "unsquashfs"
        args = ["-f", "-n", "-d", conf.target.system_root, self.osimg_path]

        try:
            rc = execWithRedirect(cmd, args)
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

        # This will cleanup files that are by default in the SquashFS image
        # and are not wanted in the target system. The parent directories will be preserved
        # Ideally those should be not present in the image in the first place.
        find_arguments = ["/boot/loader", "/tmp", "-mindepth", "1", "-delete"]
        execInSysroot("find", find_arguments)
        # Live needs to create the rescue image before bootloader is written
        self._create_rescue_image()



    @property
    def space_required(self):
        from pyanaconda.modules.payloads.base.utils import get_dir_size
        return Size(get_dir_size("/") * 1024)
