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
from pyanaconda import isys

from . import *

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil

import logging
log = logging.getLogger("anaconda")

from pyanaconda.errors import *
from pyanaconda import progress
from pyanaconda.storage.size import Size
from pyanaconda.threads import threadMgr, AnacondaThread

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class LiveImagePayload(ImagePayload):
    """ A LivePayload copies the source image onto the target system. """
    def setup(self, storage):
        super(LiveImagePayload, self).setup(storage)

        # Mount the live device and copy from it instead of the overlay at /
        osimg = storage.devicetree.getDeviceByPath(self.data.method.partition)
        if not stat.S_ISBLK(os.stat(osimg.path)[stat.ST_MODE]):
            exn = PayloadSetupError("%s is not a valid block device" % (self.data.method.partition,))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        isys.mount(osimg.path, INSTALL_TREE, fstype="auto", readOnly=True)

    def preInstall(self, packages=None, groups=None):
        """ Perform pre-installation tasks. """
        super(LiveImagePayload, self).preInstall(packages=packages, groups=groups)
        progress.send_message(_("Installing software") + (" %d%%") % (0,))

    def progress(self):
        """Monitor the amount of disk space used on the target and source and
           update the hub's progress bar.
        """
        source = os.statvfs(INSTALL_TREE)
        source_size = source.f_frsize * (source.f_blocks - source.f_bfree)
        mountpoints = self.storage.mountpoints.copy()
        while self.pct < 100:
            dest_size = 0
            for mnt in mountpoints:
                mnt_stat = os.statvfs(ROOT_PATH+mnt)
                dest_size += mnt_stat.f_frsize * (mnt_stat.f_blocks - mnt_stat.f_bfree)

            with self.pct_lock:
                self.pct = int(100 * dest_size / source_size)

            progress.send_message(_("Installing software") + (" %d%%") % (min(100,self.pct),))
            sleep(0.777)

    def install(self):
        """ Install the payload. """
        self.pct_lock = Lock()
        self.pct = 0
        threadMgr.add(AnacondaThread(name="AnaLiveProgressThread",
                                     target=self.progress))

        cmd = "rsync"
        # preserve: permissions, owners, groups, ACL's, xattrs, times,
        #           symlinks, hardlinks
        # go recursively, include devices and special files, don't cross
        # file system boundaries
        args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/",
                "--exclude", "/sys/", INSTALL_TREE+"/", ROOT_PATH]
        try:
            rc = iutil.execWithRedirect(cmd, args,
                                        stderr="/dev/tty5", stdout="/dev/tty5")
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
        progressThread = threadMgr.get("AnaLiveProgressThread")
        if progressThread:
            progressThread.join()

    def postInstall(self):
        """ Perform post-installation tasks. """
        progress.send_message(_("Performing post-install setup tasks"))
        isys.umount(INSTALL_TREE, removeDir=True)

        super(LiveImagePayload, self).postInstall()
        self._recreateInitrds()

    @property
    def spaceRequired(self):
        return Size(bytes=iutil.getDirSize("/")*1024)
