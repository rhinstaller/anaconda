#
# lvmErrors.py: lvm error exceptions
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
# Red Hat Author(s): Peter Jones <pjones@redhat.com>
#

"""Exceptions for use in lvm operations."""

import string
from lvm import output

class LvmError(Exception):
    """An error occurred with lvm."""
    def __init__(self, command, name=None):
        self.command = command
        self.name = name
        self.log = self.getLvmOutput()

    def getLvmOutput(self):
        f = open(output, "r")
        lines = reduce(lambda x,y: x + [string.strip(y),], f.readlines(), [])
        lines = string.join(reduce(lambda x,y: x + ["   %s" % (y,)], \
                                    lines, []), "\n")
        return lines

    def __str__(self):
        s = ""
        if not self.name is None:
            s = " for device %s" % (self.name,)
        return "%s failed%s\nLog:\n%s" % (self.command, s, self.log)

class LVCreateError(LvmError):
    def __init__(self, vgname, lvname, size):
        self.vgname = vgname
        self.lvname = lvname
        self.size = size
        self.log = self.getLvmOutput()

    def __str__(self):
        return "lvcreate of %d Megabyte lv \"%s\" on vg \"%s\" failed\n" \
               "Log:\n%s" % ( \
            self.size, self.lvname, self.vgname, self.log)

class LVRemoveError(LvmError):
    def __init__(self, vgname, lvname):
        self.vgname = vgname
        self.lvname = lvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return "lvremove of lv \"%s\" from vg \"%s\" failed\nLog:\n%s" % ( \
            self.lvname, self.vgname, self.log)

class LVResizeError(LvmError):
    def __init__(self, vgname, lvname):
        self.vgname = vgname
        self.lvname = lvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return "lvresize of lv \"%s\" from vg \"%s\" failed\nLog:\n%s" % ( \
            self.lvname, self.vgname, self.log)

class VGCreateError(LvmError):
    def __init__(self, vgname, PESize, nodes):
        self.vgname = vgname
        self.PESize = PESize
        self.nodes = nodes
        self.log = self.getLvmOutput()

    def __str__(self):
        nodes = string.join(self.nodes, ' ')
        return "vgcreate failed creating vg \"%s\" (PESize=%dkB) on PVs: %s\n" \
               "Log:\n%s" % ( \
            self.vgname, self.PESize, nodes, self.log)

class VGRemoveError(LvmError):
    def __init__(self, vgname):
        self.vgname = vgname
        self.log = self.getLvmOutput()

    def __str__(self):
        return "vgremove of vg \"%s\" failed\nLog:\n%s" % ( \
            self.vgname, self.log)

class PVRemoveError(LvmError):
    def __init__(self, pvname):
        self.pvname = pvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return "pvremove of pv \"%s\" failed\nLog:\n%s" % ( \
            self.pvname, self.log)

class PVCreateError(LvmError):
    def __init__(self, pvname):
        self.pvname = pvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return "pvcreate of pv \"%s\" failed\nLog:\n%s" % ( \
            self.pvname, self.log)

