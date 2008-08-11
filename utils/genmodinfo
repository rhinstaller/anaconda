#!/usr/bin/python
#
# genmodinfo
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

import commands
import os
import string
import sys

uname = os.uname()[2]

if len(sys.argv) > 1:
    path = sys.argv[1]
else:
    path = '/lib/modules/%s' % (uname,)
    
mods = {}
for root, dirs, files in os.walk(path):
    for file in files:
        mods[file] = os.path.join(root,file)

modules = { 'scsi_hostadapter' : [ 'block' ], 'eth' : [ 'networking'] }
blacklist = ("floppy", "scsi_mod", "libiscsi")

list = {}

for modtype in modules.keys():
    list[modtype] = {}
    for file in modules[modtype]:
        try:
            f = open('%s/modules.%s' % (path,file),'r')
        except:
            continue
        lines = f.readlines()
        f.close()
        for line in lines:
            line = line.strip()
            if mods.has_key(line):
                desc = commands.getoutput("modinfo -F description %s" % (mods[line])).split("\n")[0]
                desc = desc.strip()
                modname = line[:-3]
                if modname in blacklist:
                    continue
                if desc and len(desc) > 65:
                    desc = desc[:65]
                if not desc:
                    desc = "%s driver" % (modname,)
                modinfo = """
%s
        %s
        "%s"
""" % (modname, modtype, desc)
                list[modtype][modname] = modinfo

print "Version 0"
for type in list.keys():
    modlist = list[type].keys()
    modlist.sort()
    for m in modlist:
        print list[type][m]
