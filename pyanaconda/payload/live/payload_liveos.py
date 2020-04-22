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
import functools
import glob
import os
import stat
from threading import Lock
from time import sleep

from blivet.size import Size
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_OS, INSTALL_TREE, THREAD_LIVE_PROGRESS
from pyanaconda.core.i18n import _
from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.errors import PayloadInstallError, PayloadSetupError
from pyanaconda.progress import progressQ
from pyanaconda.threading import threadMgr, AnacondaThread

log = get_packaging_logger()

__all__ = ["LiveOSPayload"]


class LiveOSPayload(Payload):
    """ A LivePayload copies the source image onto the target system. """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Used to adjust size of sysroot when files are already present
        self._adj_size = 0
        self.pct = 0
        self.pct_lock = None
        self.source_size = 1

        self._kernel_version_list = []

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_LIVE_OS

    def setup(self):
        super().setup()

        # Mount the live device and copy from it instead of the overlay at /
        osimg = payload_utils.resolve_device(self.data.method.partition)
        if not osimg:
            raise PayloadInstallError("Unable to find osimg for %s" % self.data.method.partition)

        osimg_path = payload_utils.get_device_path(osimg)
        if not stat.S_ISBLK(os.stat(osimg_path)[stat.ST_MODE]):
            exn = PayloadSetupError("%s is not a valid block device" %
                                    (self.data.method.partition,))
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

    def progress(self):
        """Monitor the amount of disk space used on the target and source and
           update the hub's progress bar.
        """
        mountpoints = payload_utils.get_mount_points()
        last_pct = -1

        while self.pct < 100:
            dest_size = 0
            for mnt in mountpoints:
                mnt_stat = os.statvfs(conf.target.system_root + mnt)
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
        args = ["-pogAXtlHrDx", "--exclude", "/dev/", "--exclude", "/proc/", "--exclude", "/tmp/*",
                "--exclude", "/sys/", "--exclude", "/run/", "--exclude", "/boot/*rescue*",
                "--exclude", "/boot/loader/", "--exclude", "/boot/efi/loader/",
                "--exclude", "/etc/machine-id", INSTALL_TREE + "/", conf.target.system_root]
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
        self._create_rescue_image()

    def _create_rescue_image(self):
        """Create the rescue initrd images for each installed kernel. """
        # Always make sure the new system has a new machine-id, it won't boot without it
        # (and nor will some of the subsequent commands like grub2-mkconfig and kernel-install)
        log.info("Generating machine ID")
        if os.path.exists(conf.target.system_root + "/etc/machine-id"):
            os.unlink(conf.target.system_root + "/etc/machine-id")
        util.execInSysroot("systemd-machine-id-setup", [])

        if os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            use_nkp = True
        else:
            log.debug("new-kernel-pkg does not exist, calling scripts directly.")
            use_nkp = False

        for kernel in self.kernel_version_list:
            log.info("Generating rescue image for %s", kernel)
            if use_nkp:
                util.execInSysroot("new-kernel-pkg",
                                   ["--rpmposttrans", kernel])
            else:
                files = glob.glob(conf.target.system_root + "/etc/kernel/postinst.d/*")
                srlen = len(conf.target.system_root)
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

        # Not using BLS configuration, skip it
        if os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            return

        # Remove any existing BLS entries, they will not match the new system's
        # machine-id or /boot mountpoint.
        for file in glob.glob(conf.target.system_root + "/boot/loader/entries/*.conf"):
            log.info("Removing old BLS entry: %s", file)
            os.unlink(file)

        # Create new BLS entries for this system
        for kernel in self.kernel_version_list:
            log.info("Regenerating BLS info for %s", kernel)
            util.execInSysroot("kernel-install", ["add",
                                                  kernel,
                                                  "/lib/modules/{0}/vmlinuz".format(kernel)])

    @property
    def space_required(self):
        from pyanaconda.modules.payloads.base.utils import get_dir_size
        return Size(get_dir_size("/") * 1024)

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
