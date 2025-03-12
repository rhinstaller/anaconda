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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import shlex
import shutil
from collections import namedtuple

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import execReadlines, execWithRedirect

log = get_module_logger(__name__)


class GrubbyInfoError(Exception):
    pass


def unquote(s):
    return ' '.join(shlex.split(s))


def run_grubby(args=None):
    """ Run grubby and retrieve the kernel, initrd and boot arguments

        :param list args: Arguments to pass to grubby.
        :returns: kernel path, initrd path, root device, kernel cmdline args.
        :rtype: namedtuple
        :raises: some error on failure

        The returned namedtuple contains the following attributes:
            kernel, initrd, root, args
    """
    boot_info_fields = ["kernel", "initrd", "root", "args"]
    boot_info_class = namedtuple("BootInfo", boot_info_fields)
    boot_info_args = {}

    if not args:
        args = ["--info", "DEFAULT"]

    # Run grubby and fill in the boot_info with the first values seen, exit the
    # loop when all of the needed values have been gathered.
    try:

        for line in execReadlines("grubby", args, root=conf.target.system_root):
            key, _sep, value = line.partition("=")
            value = unquote(value)

            if key in boot_info_fields:
                boot_info_args[key] = value
                boot_info_fields.remove(key)

            if not boot_info_fields:
                break
    except OSError as e:
        log.error("run_grubby failed: %s", e)
        raise GrubbyInfoError(e) from e

    if boot_info_fields:
        raise GrubbyInfoError("Missing values: %s" % ", ".join(boot_info_fields))

    # There could be multiple initrd images defined for a boot entry, but
    # the kexec command line tool only supports passing a single initrd.
    if "initrd" in boot_info_args:
        boot_info_args["initrd"] = boot_info_args["initrd"].split(" ")[0]

    boot_info = boot_info_class(**boot_info_args)
    log.info("grubby boot info for (%s): %s", args, boot_info)
    return boot_info


def setup_kexec():
    """ Setup kexec to use the new kernel and default bootloader entry

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
    shutil.copy2(conf.target.system_root + boot_info.kernel, "/tmp/vmlinuz-kexec-reboot")
    shutil.copy2(conf.target.system_root + boot_info.initrd, "/tmp/initrd-kexec-reboot")

    append = "root=%s %s" % (boot_info.root, boot_info.args)
    args = ["--initrd", "/tmp/initrd-kexec-reboot", "--append", append, "-l", "/tmp/vmlinuz-kexec-reboot"]
    try:
        rc = execWithRedirect("kexec", args)
    except OSError as e:
        log.error("setup_kexec failed: %s", e)
    if rc != 0:
        log.error("setup_kexec failed with rc=%d: See program.log for output", rc)
