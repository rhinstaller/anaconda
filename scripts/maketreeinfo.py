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


section='general'
pd="packagedir"
c=ConfigParser.ConfigParser()

if data["outfile"] is None:
    f = sys.stdout
else:
    # If there is no file, then c will be empty :)
    f = open(data["outfile"], "r+")
    c.read(f)

if not c.has_section(section):
    c.add_section(section)

for k,v in data.items(): 
    if k != 'outfile':
        if k != pd:
            c.set(section,k,v)
        else:
            if c.has_option(section, pd):
                # We should apend to an existing list
                prevVal = c.get(section, pd)
                # The value should not be blank, but just in case.
                # This is to avoid having a line that begins with coma.
                if prevVal == "":
                    c.set(section, pd, v)
                else:
                    c.set(section, pd, "%s,%s"%(prevVal, v))
            else:
                c.set(section, pd, v)
c.write(f)
