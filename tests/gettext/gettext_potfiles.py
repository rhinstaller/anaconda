#!/usr/bin/python2

import os, sys, subprocess

# The xpath in this file is simple enough that Python's built-in
# ElementTree can handle it, so we don't need lxml here
import xml.etree.ElementTree as ET

if "top_srcdir" not in os.environ:
    sys.stderr.write("$top_srcdir must be defined in the test environment\n")
    # This return code tells the automake test driver that the test setup failed
    sys.exit(99)

# Ensure that tests/lib is in sys.path
testlibpath = os.path.abspath(os.path.join(os.environ["top_srcdir"], "tests/lib"))
if testlibpath not in sys.path:
    sys.path.append(testlibpath)

from filelist import testfilelist

success = True

def check_potfile(checkfile, potlist):
    global success

    potcheckfile = None
    if checkfile.endswith(".py"):
        # Check whether the file imports the i18n module
        if subprocess.call(["grep", "-q", "^from pyanaconda.i18n import", checkfile]) == 0:
            potcheckfile = checkfile
    elif checkfile.endswith(".c"):
        # Check whether the file includes intl.h
        if subprocess.call(["grep", "-q", "#include .intl\\.h.", checkfile]) == 0:
            potcheckfile = checkfile
    elif checkfile.endswith(".glade"):
        # Look for a "translatable=yes" attribute
        if ET.parse(checkfile).findall(".//*[@translatable='yes']"):
            potcheckfile = checkfile
    elif checkfile.endswith(".desktop.in"):
        # These are handled by intltool, make sure the .h version is present
        potcheckfile = checkfile + ".h"

    if not potcheckfile:
        return

    # Compute the path relative to top_srcdir
    potcheckfile = os.path.relpath(potcheckfile, os.environ["top_srcdir"])

    if potcheckfile not in potlist:
        sys.stderr.write("%s not in POTFILES.in\n" % potcheckfile)
        success = False

# Read in POTFILES.in, skip comments and blank lines
POTFILES = set()
with open(os.path.join(os.environ["top_srcdir"], "po", "POTFILES.in")) as f:
    for line in (line.strip() for line in f):
        if line and not line.startswith("#"):
            POTFILES.add(line)

# Walk the source tree and look for files with translatable strings
for testfile in testfilelist():
    check_potfile(testfile, POTFILES)

if not success:
    sys.exit(1)
