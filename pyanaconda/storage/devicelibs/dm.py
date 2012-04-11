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

def dm_setup(args):
    ret = iutil.execWithRedirect("dmsetup", args,
                                 stdout = "/dev/tty5",
                                 stderr = "/dev/tty5")
    if ret:
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
    # first, try sysfs
    name_file = "/sys/class/block/%s/dm/name" % dm_node
    try:
        name = open(name_file).read().strip()
    except IOError:
        # next, try pyblock
        name = block.getNameFromDmNode(dm_node)

    return name

def dm_node_from_name(map_name):
    named_path = "/dev/mapper/%s" % map_name
    try:
        # /dev/mapper/ nodes are usually symlinks to /dev/dm-N
        node = os.path.basename(os.readlink(named_path))
    except OSError:
        try:
            # dm devices' names are based on the block device minor
            st = os.stat(named_path)
            minor = os.minor(st.st_rdev)
            node = "dm-%d" % minor
        except OSError:
            # try pyblock
            node = block.getDmNodeFromName(map_name)

    if not node:
        raise DMError("dm_node_from_name(%s) has failed." % node)

    return node
