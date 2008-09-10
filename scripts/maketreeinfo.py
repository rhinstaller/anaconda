#!/usr/bin/python
#
# makes a .treeinfo file.  if information isn't provided, emit some warnings.
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
# Author(s): Will Woods <wwoods@redhat.com>
#

import os,sys,string
import getopt
import time
import ConfigParser


def usage():
    args = ""
    for key in data:
        args = "%s [--%s=%s]" %(args, key, key)
    print("%s: %s" % (sys.argv[0], args))
    sys.exit(1)

# TODO: add composeid, images, etc.
# TODO: take releasestr as an option and break it up into family/variant/version?

data = {"timestamp": time.time(),
        "family": None,
        "variant": None,
        "version": None,
        "arch": None,
        "discnum": None,
        "totaldiscs": None,
        "packagedir": None,
        "outfile": None}
allDiscs = None

opts = []
for key in data.keys():
    opts.append("%s=" % (key,))
opts.append("allDiscs")

(args, extra) = getopt.getopt(sys.argv[1:], '', opts)
if len(extra) > 0:
    print("had extra args: %s" % extra)
    usage()

for (str, arg) in args:
    if str[2:] in data.keys():
        data[str[2:]] = arg
    elif str == "--allDiscs":
        allDiscs = 1
    else:
	print("unknown str of ", str)
        usage()

# Make sure timestamp is actually a float
if type(data["timestamp"]) != float:
    data["timestamp"] = float(data["timestamp"])

if data["family"] is None:
    sys.stderr.write("--family missing! This is probably bad!\n")
    data["family"] = ""

if data["variant"] is None:
    sys.stderr.write("--variant missing, but that's OK.\n")
    data["variant"] = ""

if data["version"] is None:
    sys.stderr.write("--version missing! This is probably bad!\n")
    data["version"] = ""

if data["arch"] is None:
    sys.stderr.write("--arch missing! This is probably bad!\n")
    data["arch"] = ""

if data["discnum"] is None and allDiscs is None:
    sys.stderr.write("--discnum missing; assuming disc 1\n")
    data["discnum"] = "1"

if data["totaldiscs"] is None and allDiscs is None:
    sys.stderr.write("--totaldiscs missing; assuming 1\n")
    data["totaldiscs"] = "1"

if data["packagedir"] is None:
    sys.stderr.write("--packagedir missing. This might cause some weirdness.\n")
    data["packagedir"] = ""


if data["outfile"] is None:
    f = sys.stdout
else:
    f = open(data["outfile"], "w")

section='general'
c=ConfigParser.ConfigParser()
c.add_section(section)
for k,v in data.items(): 
    if k != 'outfile':
        c.set(section,k,v)
c.write(f)
