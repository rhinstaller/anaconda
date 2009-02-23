
import os

import iutil
from errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def name_from_dm_node(dm_node):
    st = os.stat("/dev/%s" % dm_node)
    major = os.major(st.st_rdev)
    minor = os.minor(st.st_rdev)
    name = iutil.execWithCapture("dmsetup",
                                 ["info", "--columns",
                                  "--noheadings", "-o", "name",
                                  "-j", str(major), "-m", str(minor)],
                                 stderr="/dev/null")
    log.debug("name_from_dm(%s) returning '%s'" % (dm_node, name.strip()))
    return name.strip()

def dm_node_from_name(map_name):
    devnum = iutil.execWithCapture("dmsetup",
                                   ["info", "--columns",
                                    "--noheadings",
                                    "-o", "devno",
                                    map_name],
                                    stderr="/dev/null")
    (major, sep, minor) = devnum.strip().partition(":")
    if not sep:
        raise DMError("dm device does not exist")

    dm_node = "dm-%d" % int(minor)
    log.debug("dm_node_from_name(%s) returning '%s'" % (map_name, dm_node))
    return dm_node

def _get_backing_devnums_from_map(map_name):
    ret = []
    buf = iutil.execWithCapture("dmsetup",
                                ["info", "--columns",
                                 "--noheadings",
                                 "-o", "devnos_used",
                                 map_name],
                                stderr="/dev/null")
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

