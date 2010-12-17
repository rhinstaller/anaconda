#
# loop.py
# loop device functions
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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

from pyanaconda import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


def losetup(args, capture=False):
    if capture:
        exec_func = iutil.execWithCapture
        exec_kwargs = {}
    else:
        exec_func = iutil.execWithRedirect
        exec_kwargs = {"stdout": "/dev/tty5"}

    try:
        # ask losetup what this loop device's backing device is
        ret = exec_func("losetup", args,
                        stderr="/dev/tty5",
                        **exec_kwargs)
    except RuntimeError as e:
        raise LoopError(str(e))

    return ret

def get_backing_file(name):
    path = ""
    sys_path  = "/sys/class/block/%s/loop/backing_file" % name
    if os.access(sys_path, os.R_OK):
        path = open(sys_path).read().strip()

    return path

def get_loop_name(path):
    args = ["-j", path]
    buf = losetup(args, capture=True)
    if len(buf.splitlines()) > 1:
        # there should never be more than one loop device listed
        raise LoopError("multiple loops associated with %s" % path)

    name = os.path.basename(buf.split(":")[0])
    return name

def loop_setup(path):
    args = ["-f", path]
    msg = None
    try:
        msg = losetup(args)
    except LoopError as e:
        msg = str(e)

    if msg:
        raise LoopError("failed to set up loop for %s: %s" % (path, msg))

def loop_teardown(path):
    args = ["-d", path]
    msg = None
    try:
        msg = losetup(args)
    except LoopError as e:
        msg = str(e)

    if msg:
        raise DeviceError("failed to tear down loop %s: %s" % (path, msg))


