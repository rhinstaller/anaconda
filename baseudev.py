# udev.py
# Python module for querying the udev database for device information.
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
#                    Chris Lumens <clumens@redhat.com>
#

import iutil
import os

import logging
log = logging.getLogger("storage")

def udev_enumerate_devices(deviceClass="block"):
    top_dir = "/sys/class/%s" % deviceClass
    devices = []
    for dev_name in os.listdir(top_dir):
        full_path = os.path.join(top_dir, dev_name)
        link_ref = os.readlink(full_path)
        real_path = os.path.join(top_dir, link_ref)
        sysfs_path = os.path.normpath(real_path)
        devices.append(sysfs_path)
    return devices

def udev_get_device(sysfs_path):
    if not os.path.exists(sysfs_path):
        log.debug("%s does not exist" % sysfs_path)
        return None

    db_entry = sysfs_path[4:].replace("/", "\\x2f")
    db_root = "/dev/.udev/db"
    db_path = os.path.normpath("%s/%s" % (db_root, db_entry))
    if not os.access(db_path, os.R_OK):
        log.debug("db entry %s does not exist" % db_path)
        return None

    entry = open(db_path).read()
    dev = udev_parse_entry(entry)
    if dev.has_key("name"):
        # XXX why do we do this? is /sys going to move during installation?
        dev['sysfs_path'] = sysfs_path[4:]  # strip off the leading '/sys'
        dev = udev_parse_uevent_file(dev)

    # now add in the contents of the uevent file since they're handy
    return dev

def udev_get_devices(deviceClass="block"):
    udev_settle(timeout=30)
    entries = []
    for path in udev_enumerate_devices(deviceClass):
        entry = udev_get_device(path)
        if entry:
            entries.append(entry)
    return entries

def udev_parse_entry(buf):
    dev = {}

    for line in buf.splitlines():
        line.strip()
        (tag, sep, val) = line.partition(":")
        if not sep:
            continue

        if tag == "N":
            dev['name'] = val
        elif tag == "S":
            if dev.has_key('symlinks'):
                dev['symlinks'].append(val)
            else:
                dev['symlinks'] = [val]
        elif tag == "E":
            if val.count("=") > 1 and val.count(" ") > 0:
                # eg: LVM2_LV_NAME when querying the VG for its LVs
                vars = val.split()
                vals = []
                var_name = None
                for (index, subval) in enumerate(vars):
                    (var_name, sep, var_val) = subval.partition("=")
                    if sep:
                        vals.append(var_val)

                dev[var_name] = vals
            else:
                (var_name, sep, var_val) = val.partition("=")
                if not sep:
                    continue

                dev[var_name] = var_val

    return dev

def udev_parse_uevent_file(dev):
    path = os.path.normpath("/sys/%s/uevent" % dev['sysfs_path'])
    if not os.access(path, os.R_OK):
        return dev

    with open(path) as f:
        for line in f.readlines():
            (key, equals, value) = line.strip().partition("=")
            if not equals:
                continue

            dev[key] = value

    return dev

def udev_settle(timeout=None):
    argv = ["settle"]
    if timeout:
        argv.append("--timeout=%d" % int(timeout))

    iutil.execWithRedirect("udevadm", argv, stderr="/dev/null", searchPath=1)

def udev_trigger(subsystem=None):
    argv = ["trigger"]
    if subsystem:
        argv.append("--subsystem-match=%s" % subsystem)

    iutil.execWithRedirect("udevadm", argv, stderr="/dev/null", searchPath=1)
