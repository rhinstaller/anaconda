#!/usr/bin/python
#
# makes a .discinfo file.  if information isn't provided, prompts for it
#
# Copyright 2002  Red Hat, Inc.
#
# License: GPL
#

import os,sys,string
import getopt
import time


def usage():
    args = ""
    for key in data:
        args = "%s [--%s=%s]" %(args, key, key)
    print "%s: %s" % (sys.argv[0], args)
    sys.exit(1)

data = {"timestamp": None,
        "releasestr": None,
        "arch": None,
        "discNum": None,
        "baseDir": None,
        "packagesDir": None,
        "pixmapsDir": None,
        "outfile": None}
allDiscs = None

opts = []
for key in data.keys():
    opts.append("%s=" % (key,))
opts.append("allDiscs")

(args, extra) = getopt.getopt(sys.argv[1:], '', opts)
if len(extra) > 0:
    print "had extra args: %s" % extra
    usage()

for (str, arg) in args:
    if str[2:] in data.keys():
        data[str[2:]] = arg
    elif str == "--allDiscs":
        allDiscs = 1
    else:
	print "unknown str of ", str
        usage()

if data["timestamp"] is None:
    print >> sys.stderr, "timestamp not specified; using the current time"
    data["timestamp"] = time.time()
else:
    data["timestamp"] = float(data["timestamp"])

if data["releasestr"] is None:
    print "What should be the release name associated with this disc?"
    data["releasestr"] = sys.stdin.readline()[:-1]

if data["arch"] is None:
    print "What arch is this disc for?"
    data["arch"] = sys.stdin.readline()[:-1]
    
if data["discNum"] is None and allDiscs is None:
    print >> sys.stderr, "No disc number specified; assuming disc 1"
    data["discNum"] = "1"

if data["baseDir"] is None:
    print "Where is the comps file located?"
    data["baseDir"] = sys.stdin.readline()[:-1]

if data["packagesDir"] is None:
    print "Where are the packages located?"
    data["packagesDir"] = sys.stdin.readline()[:-1]

if data["pixmapsDir"] is None:
    print "Where are the images located?"
    data["pixmapsDir"] = sys.stdin.readline()[:-1]


if data["outfile"] is None:
    f = sys.stdout
else:
    f = open(data["outfile"], "w")

f.write("%f\n" % data["timestamp"])
f.write("%s\n" % data["releasestr"])
f.write("%s\n" % data["arch"])
if allDiscs is None:
    f.write("%s\n" % data["discNum"])
else:
    f.write("0\n")
f.write("%s\n" % data["baseDir"])
f.write("%s\n" % data["packagesDir"])
f.write("%s\n" % data["pixmapsDir"])

    
