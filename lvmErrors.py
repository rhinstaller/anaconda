#
# lvmErrors.py: lvm error exceptions
#
# Peter Jones <pjones@redhat.com>
#
# Copyright 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Exceptions for use in lvm operations."""

import string

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

class LVRemoveError(LvmError):
    def __init__(self, vgname, lvname):
        self.vgname = vgname
        self.lvname = lvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return 'lvremove of lv "%s" from vg "%s" failed\nLog:\n%s' % ( \
            self.lvname, self.vgname, self.log)

class VGRemoveError(LvmError):
    def __init__(self, vgname):
        self.vgname = vgname
        self.log = self.getLvmOutput()

    def __str__(self):
        return 'vgremove of vg "%s" failed\nLog:\n%s' % ( \
            self.vgname, self.log)

class PVRemoveError(LvmError):
    def __init__(self, pvname):
        self.pvname = pvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return 'pvremove of pv "%s" failed\nLog:\n%s' % ( \
            self.pvname, self.log)

class PVCreateError(LvmError):
    def __init__(self, pvname):
        self.pvname = pvname
        self.log = self.getLvmOutput()

    def __str__(self):
        return 'pvcreate of pv "%s" failed\nLog:\n%s' % ( \
            self.pvname, self.log)
