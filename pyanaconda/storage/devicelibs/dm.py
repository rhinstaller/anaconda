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
import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

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

def dm_is_multipath(info):
    major = None
    minor = None

    if info.has_key('MAJOR'):
        major = info['MAJOR']
    elif info.has_key('DM_MAJOR'):
        major = info['DM_MAJOR']
    if info.has_key('MINOR'):
        minor = info['MINOR']
    elif info.has_key('DM_MINOR'):
        minor = info['DM_MINOR']

    if major is None or minor is None:
        return False

    for map in block.dm.maps():
        dev = map.dev
        if dev.major == int(major) and dev.minor == int(minor):
            for table in map.table:
                if table.type == 'multipath':
                    return True

def _get_backing_devnums_from_map(map_name):
    ret = []
    buf = iutil.execWithCapture("dmsetup",
                                ["info", "--columns",
                                 "--noheadings",
                                 "-o", "devnos_used",
                                 map_name],
                                stderr="/dev/tty5")
    dev_nums = buf.split()
    for dev_num in dev_nums:
        (major, colon, minor) = dev_num.partition(":")
        ret.append((int(major), int(minor)))

    return ret

def get_backing_devnums(dm_node):
    #dm_node = dm_node_from_name(map_name)
    if not dm_node:
        return None

    top_dir = "/sys/block"
    backing_devs = os.listdir("%s/%s/slaves/" % (top_dir, dm_node))
    dev_nums = []
    for backing_dev in backing_devs:
        dev_num = open("%s/%s/dev" % (top_dir, backing_dev)).read().strip()
        (_major, _minor) = dev_num.split(":")
        dev_nums.append((int(_major), int(_minor)))

    return dev_nums

def get_backing_devs_from_name(map_name):
    dm_node = dm_node_from_name(map_name)
    if not dm_node:
        return None

    slave_devs = os.listdir("/sys/block/virtual/%s" % dm_node)
    return slave_devs

