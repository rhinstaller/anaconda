#!/usr/bin/python

import os
import sys

# for testing
if (os.path.exists('isys')):
    sys.path.append('isys')

sys.path.append('/usr/lib/anaconda')

import isys
from sys import argv

def usage():
    print "usage: losetup [-d] /dev/loopN [image]"
    sys.exit(1)

if len(argv) < 3:
    usage()

if argv[1] == "-d" and len(argv[2]) > 4 and argv[2][-5:-1] == "loop":
    try:
        isys.makeDevInode(argv[2][-5:], argv[2])
        isys.unlosetup(argv[2])
    except SystemError, (errno, msg):
        print msg
        sys.exit (1)
    sys.exit(0)

if len(argv[1]) > 4 and argv[1][-5:-1] == "loop":
    try:
        isys.makeDevInode(argv[1][-5:], argv[1])
        isys.losetup(argv[1], argv[2])
    except SystemError, (errno, msg):
        print msg
        sys.exit (1)
    sys.exit(0)

usage()
