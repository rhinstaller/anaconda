#!/usr/bin/python

"""Walks path given on the command line for .pyc and .pyo files, changing
the mtime in the header to 0, so it will match the .py file on the cramfs"""

import os
import sys
import getopt

debug = 0

def usage():
    print 'usage: %s /path/to/walk/and/fix' %sys.argv[0]
    sys.exit(1)

def visit(arg, d, files):
    for filen in files:
        if not (filen.endswith('.pyc') or filen.endswith('.pyo')):
            continue
        path = os.sep.join((d, filen))
        #print 'fixing mtime', path
        f = open(path, 'r+')
        f.seek(4)
        f.write('\0\0\0\0')
        f.close()

if __name__ == '__main__':
    (args, extra) = getopt.getopt(sys.argv[1:], '', "debug")

    if len(extra) < 1:
        usage()

    for arg in args:
        if arg == "--debug":
            debug = 1

    dir = extra[0]

    if not os.path.isdir(dir):
        usage()

    os.path.walk(dir, visit, None)

