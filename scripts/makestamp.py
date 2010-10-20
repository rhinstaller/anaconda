#!/usr/bin/python
#
# makes a .discinfo file.  if information isn't provided, prompts for it
#
# Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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

import os,sys,string
import getopt
import time


def usage():
    args = ""
    for key in data:
        args = "%s [--%s=%s]" %(args, key, key)
    print("%s: %s" % (sys.argv[0], args))
    sys.exit(1)

data = {"timestamp": None,
        "releasestr": None,
        "arch": None,
        "outfile": None}

opts = []
for key in data.keys():
    opts.append("%s=" % (key,))

(args, extra) = getopt.getopt(sys.argv[1:], '', opts)
if len(extra) > 0:
    print("had extra args: %s" % extra)
    usage()

for (str, arg) in args:
    if str[2:] in data.keys():
        data[str[2:]] = arg
    else:
	print("unknown str of ", str)
        usage()

if data["timestamp"] is None:
    sys.stderr.write("timestamp not specified; using the current time\n")
    data["timestamp"] = time.time()
else:
    data["timestamp"] = float(data["timestamp"])

if data["releasestr"] is None:
    print("What should be the release name associated with this disc?\n")
    data["releasestr"] = sys.stdin.readline()[:-1]

if data["arch"] is None:
    print("What arch is this disc for?")
    data["arch"] = sys.stdin.readline()[:-1]

if data["outfile"] is None:
    f = sys.stdout
else:
    f = open(data["outfile"], "w")

f.write("%f\n" % data["timestamp"])
f.write("%s\n" % data["releasestr"])
f.write("%s\n" % data["arch"])
