# kexec.py
#
# Setup kexec to restart the system using the default bootloader entry
#
# Copyright (C) 2015 Red Hat, Inc.
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
import shutil
from collections import namedtuple

from pyanaconda.iutil import getSysroot, execReadlines, execWithRedirect
from pyanaconda.simpleconfig import unquote

import logging
log = logging.getLogger("anaconda")

class GrubbyInfoError(Exception):
    pass

_BootInfo = namedtuple("BootInfo", ["kernel", "initrd", "root", "args"])

def run_grubby(args=None):
    """ Run grubby and retrieve the kernel, initrd and boot arguments

        :param list args: Arguments to pass to grubby.
        :returns: kernel path, initrd path, root device, kernel cmdline args.
        :rtype: namedtuple
        :raises: some error on failure

        The returned namedtuple contains the following attributes:
            kernel, initrd, root, args
    """
    boot_info = _BootInfo()
    attrs = list(_BootInfo._fields)

    if not args:
        args = ["--info", "DEFAULT"]

    # Run grubby and fill in the boot_info with the first values seen, exit the
    # loop when all of the needed values have been gathered.
    try:

        for line in execReadlines("grubby", args, root=getSysroot()):
            key, _sep, value = line.partition("=")
            value = unquote(value)
            if key in attrs:
                setattr(boot_info, key, value)
                attrs.remove(key)
            if not attrs:
                break
    except OSError as e:
        log.error("run_grubby failed: %s", e)
        raise GrubbyInfoError(e)

    if len(attrs) > 0:
        raise GrubbyInfoError("Missing values: %s" % ", ".join(attrs))

    log.info("grubby boot info for (%s): %s", args, boot_info)
    return boot_info


def setup_kexec(extra_args=None):
    """ Setup kexec to use the new kernel and default bootloader entry

        :param list extra_args: Extra arguments to pass to kexec

        This uses grubby to determine the bootloader arguments from the default entry,
        and then sets up kexec so that reboot will use the new kernel and initrd instead
        of doing a full reboot.

        .. note::
            Once kexec is called there is nothing else to do, the reboot code already handles
            having kexec setup.
    """
    try:
        boot_info = run_grubby()
    except GrubbyInfoError:
        # grubby couldn't find a default entry, use the first one instead
        try:
            boot_info = run_grubby(["--info", "ALL"])
        except GrubbyInfoError:
            # Grubby can't get the bootloader's info, kexec won't work.
            log.error("kexec reboot setup failed, grubby could not get bootloader info.")
            return

    # Copy the kernel and initrd to /tmp/
    shutil.copy2(getSysroot()+boot_info.kernel, "/tmp/vmlinuz-kexec-reboot")
    shutil.copy2(getSysroot()+boot_info.initrd, "/tmp/initrd-kexec-reboot")

    append = "root=%s %s" % (boot_info.root, boot_info.args)
    args = ["--initrd", "/tmp/initrd-kexec-reboot", "--append", append, "-l", "/tmp/vmlinuz-kexec-reboot"]
    try:
        rc = execWithRedirect("kexec", args)
    except OSError as e:
        log.error("setup_kexec failed: %s", e)
    if rc != 0:
        log.error("setup_kexec failed with rc=%d: See program.log for output", rc)
