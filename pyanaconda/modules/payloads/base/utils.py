#
# Utility functions shared for the whole payload module.
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
import functools
import glob
import os
import stat

from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.util import mkdirChain, execWithRedirect
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.payload.utils import version_cmp

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def create_root_dir(sysroot):
    """Create root directory on the installed system."""
    mkdirChain(os.path.join(sysroot, "root"))


def write_module_blacklist(sysroot):
    """Create module blacklist based on the user preference.

    Copy modules from modprobe.blacklist=<module> on cmdline to
    /etc/modprobe.d/anaconda-blacklist.conf so that modules will
    continue to be blacklisted when the system boots.
    """
    if "modprobe.blacklist" not in kernel_arguments:
        return

    mkdirChain(os.path.join(sysroot, "etc/modprobe.d"))
    with open(os.path.join(sysroot, "etc/modprobe.d/anaconda-blacklist.conf"), "w") as f:
        f.write("# Module blacklists written by anaconda\n")
        for module in kernel_arguments.get("modprobe.blacklist").split():
            f.write("blacklist %s\n" % module)


def get_dir_size(directory):
    """Get the size of a directory and all its subdirectories.

    :param str directory: the name of the directory to find the size of
    :return: the size of the directory in kilobytes
    """
    def get_subdir_size(directory):
        # returns size in bytes
        try:
            mydev = os.lstat(directory)[stat.ST_DEV]
        except OSError as e:
            log.debug("failed to stat %s: %s", directory, e)
            return 0

        try:
            dirlist = os.listdir(directory)
        except OSError as e:
            log.debug("failed to listdir %s: %s", directory, e)
            return 0

        dsize = 0
        for f in dirlist:
            curpath = '%s/%s' % (directory, f)
            try:
                sinfo = os.lstat(curpath)
            except OSError as e:
                log.debug("failed to stat %s/%s: %s", directory, f, e)
                continue

            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if os.path.ismount(curpath):
                    continue
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += get_subdir_size(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]

        return dsize
    return get_subdir_size(directory) // 1024


def get_kernel_version_list(root_path):
    files = glob.glob(root_path + "/boot/vmlinuz-*")
    files.extend(
        glob.glob(root_path + "/boot/efi/EFI/{}/vmlinuz-*".format(conf.bootloader.efi_dir))
    )

    kernel_version_list = sorted((f.split("/")[-1][8:] for f in files
                                  if os.path.isfile(f) and "-rescue-" not in f),
                                 key=functools.cmp_to_key(version_cmp))
    return kernel_version_list


def create_rescue_image(root, kernel_version_list):
    """Create the rescue initrd images for each kernel."""
    # Always make sure the new system has a new machine-id, it won't boot without it
    # (and nor will some of the subsequent commands like grub2-mkconfig and kernel-install)
    log.info("Generating machine ID")
    if os.path.exists(root + "/etc/machine-id"):
        os.unlink(root + "/etc/machine-id")
    execWithRedirect("systemd-machine-id-setup", [], root=root)

    if os.path.exists(root + "/usr/sbin/new-kernel-pkg"):
        use_nkp = True
    else:
        log.warning("new-kernel-pkg does not exist - grubby wasn't installed?")
        use_nkp = False

    for kernel in kernel_version_list:
        log.info("Generating rescue image for %s", kernel)
        if use_nkp:
            execWithRedirect("new-kernel-pkg", ["--rpmposttrans", kernel], root=root)
        else:
            files = glob.glob(root + "/etc/kernel/postinst.d/*")
            srlen = len(root)
            files = sorted([f[srlen:] for f in files if os.access(f, os.X_OK)])
            for file in files:
                execWithRedirect(file, [kernel, "/boot/vmlinuz-%s" % kernel], root=root)
