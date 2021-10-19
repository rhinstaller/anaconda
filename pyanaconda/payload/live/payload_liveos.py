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
from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_OS, INSTALL_TREE
from pyanaconda.core.i18n import _
from pyanaconda.modules.payloads.source.live_os.initialization import DetectLiveOSImageTask, \
    SetUpLiveOSSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
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

    def setup(self):
        # Mount the live device and copy from it instead of the overlay at /
        task = DetectLiveOSImageTask()
        image_path = task.run()

        task = SetUpLiveOSSourceTask(
            image_path=image_path,
            target_mount=INSTALL_TREE
        )
        task.run()

        # Grab the kernel version list now so it's available after umount
        self._update_kernel_version_list()

    def unsetup(self):
        # Unmount a previously mounted live tree
        task = TearDownMountTask(INSTALL_TREE)
        task.run()

    def pre_install(self):
        """ Perform pre-installation tasks. """
        super().pre_install()
        progressQ.send_message(_("Installing software") + (" %d%%") % (0,))

    @property
    def space_required(self):
        from pyanaconda.modules.payloads.base.utils import get_dir_size
        return Size(get_dir_size("/") * 1024)
