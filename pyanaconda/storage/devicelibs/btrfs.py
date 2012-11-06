#
# btrfs.py
# btrfs functions
#
# Copyright (C) 2011  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): David Lehman <dlehman@redhat.com>
#

import os
import re

from pyanaconda import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def btrfs(args, capture=False):
    kwargs = {}
    kwargs["stderr"] = "/dev/tty5"
    if capture:
        exec_func = iutil.execWithCapture
    else:
        exec_func = iutil.execWithRedirect
        kwargs["stdout"] = "/dev/tty5"

    ret = exec_func("btrfs", args, **kwargs)
    if ret and not capture:
        raise BTRFSError(ret)
    return ret

def create_volume(devices, label=None, data=None, metadata=None):
    """ For now, data and metadata must be strings mkfs.btrfs understands. """
    if not devices:
        raise ValueError("no devices specified")
    elif any([not os.path.exists(d) for d in devices]):
        raise ValueError("one or more specified devices not present")

    args = []
    if data:
        args.append("--data=%s" % data)

    if metadata:
        args.append("--metadata=%s" % metadata)

    if label:
        args.append("--label=%s" % label)

    args.extend(devices)

    ret = iutil.execWithRedirect("mkfs.btrfs", args,
                                 stdout="/dev/tty5", stderr="/dev/tty5")
    if ret:
        raise BTRFSError(ret)

    return ret

# destroy is handled using wipefs

# add device

# remove device

def create_subvolume(mountpoint, name):
    if not os.path.ismount(mountpoint):
        raise ValueError("volume not mounted")

    path = os.path.normpath("%s/%s" % (mountpoint, name))
    args = ["subvol", "create", path]
    return btrfs(args)

def delete_subvolume(mountpoint, name):
    if not os.path.ismount(mountpoint):
        raise ValueError("volume not mounted")

    path = os.path.normpath("%s/%s" % (mountpoint, name))
    args = ["subvol", "delete", path]
    return btrfs(args)

def create_snapshot(source, dest):
    pass

def scan_device(path):
    return btrfs(["device", "scan", path])

# get a list of subvolumes from a mounted btrfs filesystem
def list_subvolumes(mountpoint):
    if not os.path.ismount(mountpoint):
        raise ValueError("volume not mounted")

    args = ["subvol", "list", mountpoint]
    buf = btrfs(args, capture=True)
    vols = []
    for group in re.findall(r'ID (\d+) gen \d+ top level \d+ path (.+)\n', buf):
        vols.append({"id": int(group[0]), "path": group[1]})

    return vols
