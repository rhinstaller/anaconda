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
import stat

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.constants import (
    INSTALL_TREE,
    PAYLOAD_TYPE_LIVE_OS,
    SOURCE_TYPE_LIVE_OS_IMAGE,
)
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.errors import PayloadSetupError
from pyanaconda.payload.live.payload_base import BaseLivePayload
from pyanaconda.progress import progressQ

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

    def setup(self):
        super().setup()
        # Mount the live device and copy from it instead of the overlay at /
        osimg_spec = self._get_live_os_image()

        if not osimg_spec:
            raise PayloadSetupError("No live image found!")

        osimg = payload_utils.resolve_device(osimg_spec)
        if not osimg:
            raise PayloadSetupError("Unable to find osimg for {}".format(osimg_spec))

        osimg_path = payload_utils.get_device_path(osimg)
        if not stat.S_ISBLK(os.stat(osimg_path)[stat.ST_MODE]):
            raise PayloadSetupError("{} is not a valid block device".format(osimg_spec))

        rc = payload_utils.mount(osimg_path, INSTALL_TREE, fstype="auto", options="ro")
        if rc != 0:
            raise PayloadSetupError("Failed to mount the install tree")

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

    @property
    def space_required(self):
        from pyanaconda.modules.payloads.base.utils import get_dir_size
        return Size(get_dir_size("/") * 1024)
