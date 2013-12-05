#!/usr/bin/python

import os, sys, subprocess

# The xpath in this file is simple enough that Python's built-in
# ElementTree can handle it, so we don't need lxml here
import xml.etree.ElementTree as ET

if "top_srcdir" not in os.environ:
    sys.stderr.write("$top_srcdir must be defined in the test environment\n")
    # This return code tells the automake test driver that the test setup failed
    os._exit(99)

success = True

def check_potfiles(checklist, dirname, names):
    global success

    potcheckfiles = []

    # Skip the .git directory
    if ".git" in names:
        names.remove(".git")

    # Strip the "./" component from the path name
    dirname = os.path.relpath(dirname, ".")

    for checkfile in (os.path.join(dirname, name) for name in names):
        if checkfile.endswith(".py"):
            # Check whether the file imports the i18n module
            if subprocess.call(["grep", "-q", "^from pyanaconda.i18n import", checkfile]) == 0:
                potcheckfiles.append(checkfile)
        elif checkfile.endswith(".c"):
            # Check whether the file includes intl.h
            if subprocess.call(["grep", "-q", "#include .intl\\.h.", checkfile]) == 0:
                potcheckfiles.append(checkfile)
        elif checkfile.endswith(".glade"):
            # Look for a "translatable=yes" attribute
            if ET.parse(checkfile).findall(".//*[@translatable='yes']"):
                potcheckfiles.append(checkfile)
        elif checkfile.endswith(".desktop.in"):
            # These are handled by intltool, make sure the .h version is present
            potcheckfiles.append(checkfile + ".h")

    difference = set(potcheckfiles) - checklist
    for missing in difference:
        sys.stderr.write("%s not in POTFILES.in\n" % missing)
        success = False

# Read in POTFILES.in, skip comments and blank lines
POTFILES = []
with open(os.path.join(os.environ["top_srcdir"], "po", "POTFILES.in")) as f:
    for line in (line.strip() for line in f):
        if not line or line.startswith("#"):
            continue
        POTFILES.append(line)

# Walk the source tree and look for files with translatable strings
os.chdir(os.environ["top_srcdir"])
os.path.walk(".", check_potfiles, set(POTFILES))

if not success:
    os._exit(1)
