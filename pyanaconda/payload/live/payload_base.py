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
from threading import Lock
from time import sleep

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE, THREAD_LIVE_PROGRESS
from pyanaconda.core.i18n import _
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.errors import PayloadInstallError
from pyanaconda.progress import progressQ
from pyanaconda.threading import AnacondaThread, threadMgr

log = get_packaging_logger()

__all__ = ["BaseLivePayload"]


class BaseLivePayload(Payload):
    """Base class for live payloads."""

    # Inherit abstract methods from Payload
    # pylint: disable=abstract-method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Used to adjust size of sysroot when files are already present
        self._adj_size = 0
        self.pct = 0
        self.pct_lock = None
        self.source_size = 1

        self._kernel_version_list = []

    def progress(self):
        """Monitor the amount of disk space used on the target and source and
           update the hub's progress bar.
        """
        mount_points = payload_utils.get_mount_points()
        last_pct = -1

        while self.pct < 100:
            dest_size = self._get_destination_size(mount_points)

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

    def _get_destination_size(self, mount_points):
        # FIXME: Use get_df_map/get_free_space_map.
        dest_size = 0

        for mnt in mount_points:
            mnt_path = util.join_paths(conf.target.system_root, mnt)

            if not os.path.exists(mnt_path):
                continue

            mnt_stat = os.statvfs(mnt_path)
            dest_size += mnt_stat.f_frsize * (mnt_stat.f_blocks - mnt_stat.f_bfree)

        return dest_size

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
        args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/", "--exclude", "/tmp/*",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/boot/loader/", "--exclude", "/boot/efi/loader/",
                "--exclude", "/etc/machine-id", "--exclude", "/etc/machine-info",
                INSTALL_TREE + "/", conf.target.system_root]
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
            raise PayloadInstallError(err or msg)

        # Wait for progress thread to finish
        with self.pct_lock:
            self.pct = 100
        threadMgr.wait(THREAD_LIVE_PROGRESS)

    def post_install(self):
        """ Perform post-installation tasks. """
        progressQ.send_message(_("Performing post-installation setup tasks"))
        payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        super().post_install()

    def _update_kernel_version_list(self):
        self._kernel_version_list = get_kernel_version_list(INSTALL_TREE)

    @property
    def kernel_version_list(self):
        return self._kernel_version_list
