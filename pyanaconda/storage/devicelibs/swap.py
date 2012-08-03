# swap.py
# Python module for managing swap devices.
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

import resource

from pyanaconda import iutil
import os

from ..errors import *
from . import dm

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

def mkswap(device, label=''):
    # We use -f to force since mkswap tends to refuse creation on lvs with
    # a message about erasing bootbits sectors on whole disks. Bah.
    argv = ["-f"]
    if label:
        argv.extend(["-L", label])
    argv.append(device)

    ret = iutil.execWithRedirect("mkswap", argv,
                                 stderr = "/dev/tty5",
                                 stdout = "/dev/tty5")

    if ret:
        raise SwapError("mkswap failed for '%s'" % device)

def swapon(device, priority=None):
    pagesize = resource.getpagesize()
    buf = None
    sig = None

    if pagesize > 2048:
        num = pagesize
    else:
        num = 2048

    try:
        fd = os.open(device, os.O_RDONLY)
        buf = os.read(fd, num)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except (OSError, UnboundLocalError):
            pass

    if buf is not None and len(buf) == pagesize:
        sig = buf[pagesize - 10:]
        if sig == 'SWAP-SPACE':
            raise OldSwapError
        if sig == 'S1SUSPEND\x00' or sig == 'S2SUSPEND\x00':
            raise SuspendError

    if sig != 'SWAPSPACE2':
        raise UnknownSwapError

    argv = []
    if isinstance(priority, int) and 0 <= priority <= 32767:
        argv.extend(["-p", "%d" % priority])
    argv.append(device)
        
    rc = iutil.execWithRedirect("swapon",
                                argv,
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5")

    if rc:
        raise SwapError("swapon failed for '%s'" % device)

def swapoff(device):
    rc = iutil.execWithRedirect("swapoff", [device],
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5")

    if rc:
        raise SwapError("swapoff failed for '%s'" % device)

def swapstatus(device):
    alt_dev = None
    if device.startswith("/dev/mapper/"):
        # get the real device node for device-mapper devices since the ones
        # with meaningful names are just symlinks
        try:
            alt_dev = "/dev/%s" % dm.dm_node_from_name(device.split("/")[-1])
        except DMError:
            alt_dev = None

    lines = open("/proc/swaps").readlines()
    status = False
    for line in lines:
        if not line.strip():
            continue

        swap_dev = line.split()[0]
        if swap_dev in [device, alt_dev]:
            status = True
            break

    return status

def swapSuggestion(quiet=False, hibernation=False):
    """
    Suggest the size of the swap partition that will be created.

    @param quiet: log size information
    @param hibernation: calculate swap size big enough for hibernation
    @return: calculated swap size

    """

    mem = iutil.memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
        log.info("Detected %sM of memory", mem)

    #chart suggested in the discussion with other teams
    if mem < 2048:
        swap = 2 * mem

    elif 2048 <= mem < 8192:
        swap = mem

    elif 8192 <= mem < 65536:
        swap = mem / 2

    else:
        swap = 4096

    if hibernation:
        if mem <= 65536:
            swap = mem + swap
        else:
            log.info("Ignoring --hibernation option on systems with 64 GB of RAM or more")

    if not quiet:
        log.info("Swap attempt of %sM", swap)

    return swap

