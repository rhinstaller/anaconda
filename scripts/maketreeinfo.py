#!/usr/bin/python
#
# makes a .treeinfo file.  if information isn't provided, emit some warnings.
# Author(s): Will Woods <wwoods@redhat.com>
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# License: GPL
#


import os,sys,string
import getopt
import time
import ConfigParser


def usage():
    args = ""
    for key in data:
        args = "%s [--%s=%s]" %(args, key, key)
    print "%s: %s" % (sys.argv[0], args)
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

# Make sure timestamp is actually a float
if type(data["timestamp"]) != float:
    data["timestamp"] = float(data["timestamp"])

if data["family"] is None:
    print >> sys.stderr, "--family missing! This is probably bad!"
    data["family"] = ""

if data["variant"] is None:
    print >> sys.stderr, "--variant missing, but that's OK."
    data["variant"] = ""

if data["version"] is None:
    print >> sys.stderr, "--version missing! This is probably bad!"
    data["version"] = ""

if data["arch"] is None:
    print >> sys.stderr, "--arch missing! This is probably bad!"
    data["arch"] = ""
    
if data["discnum"] is None and allDiscs is None:
    print >> sys.stderr, "--discnum missing; assuming disc 1"
    data["discnum"] = "1"

if data["totaldiscs"] is None and allDiscs is None:
    print >> sys.stderr, "--totaldiscs missing; assuming 1"
    data["totaldiscs"] = "1"

if data["packagedir"] is None:
    print >> sys.stderr, "--packagedir missing. This might cause some weirdness."
    data["packagedir"] = ""


if data["outfile"] is None:
    f = sys.stdout
else:
    f = open(data["outfile"], "w")

section='general'
c=ConfigParser.ConfigParser()

if not c.has_section(section):
    c.add_section(section)

for k,v in data.items(): 
    if k != 'outfile':
        c.set(section,k,v)

# Lets take away variant for now.
if c.has_option(section, "variant"):
    c.remove_option(section, "variant")
c.write(f)
