#
# dm.py
# device-mapper functions
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
# Author(s): Dave Lehman <dlehman@redhat.com>
#

import os

import block
from pyanaconda import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def dm_setup(args, progress=None):
    ret = iutil.execWithPulseProgress("dmsetup", args,
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     progress=progress)
    if ret.rc:
        raise DMError(ret.stderr)

def dm_create_linear(map_name, device, length, uuid):
    table = "0 %d linear %s 0" % (length, device)
    args = ["create", map_name, "--uuid", uuid, "--table", "%s" % table]
    try:
        dm_setup(args)
    except DMError as msg:
        raise DMError("dm_create_linear (%s, %d, %s) failed: %s"
                                % (map_name, length, device, msg))

def dm_remove(map_name):
    args = ["remove", map_name]
    try:
        dm_setup(args)
    except DMError as msg:
        raise DMError("dm_remove (%s) failed: %s" % (map_name, msg))

def name_from_dm_node(dm_node):
    name = block.getNameFromDmNode(dm_node)
    if name is not None:
        return name

    st = os.stat("/dev/%s" % dm_node)
    major = os.major(st.st_rdev)
    minor = os.minor(st.st_rdev)
    name = iutil.execWithCapture("dmsetup",
                                 ["info", "--columns",
                                  "--noheadings", "-o", "name",
                                  "-j", str(major), "-m", str(minor)],
                                 stderr="/dev/tty5")
    log.debug("name_from_dm(%s) returning '%s'" % (dm_node, name.strip()))
    return name.strip()

def dm_node_from_name(map_name):
    dm_node = block.getDmNodeFromName(map_name)
    if dm_node is not None:
        return dm_node

    devnum = iutil.execWithCapture("dmsetup",
                                   ["info", "--columns",
                                    "--noheadings",
                                    "-o", "devno",
                                    map_name],
                                    stderr="/dev/tty5")
    (major, sep, minor) = devnum.strip().partition(":")
    if not sep:
        raise DMError("dm device does not exist")

    dm_node = "dm-%d" % int(minor)
    log.debug("dm_node_from_name(%s) returning '%s'" % (map_name, dm_node))
    return dm_node


