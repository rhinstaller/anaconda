#!/usr/bin/python3

# Ignore any interruptible calls
# pylint: disable=interruptible-system-call

import os, sys, subprocess, tempfile

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

# from po/Makevars
XGETTEXT_OPTIONS = ["--keyword=_", "--keyword=N_", "--keyword=P_:1,2",
                    "--keyword=C_:1c,2", "--keyword=CN_:1c,2", "--keyword=CP_:1c,2,3",
                    "--from-code=UTF-8"]

def check_potfile(checkfile, potlist):
    global success

    potcheckfile = None

    _root, ext = os.path.splitext(checkfile)
    if ext in (".py", ".c", ".glade"):
        # These files are handled directly by gettext. Use xgettext to look for
        # translatable strings. If anything is written to the output file, xgettext
        # found something
        with tempfile.NamedTemporaryFile() as pofile:
            subprocess.check_call(["xgettext", "-o", pofile.name] + XGETTEXT_OPTIONS + [checkfile])
            if os.path.getsize(pofile.name) > 0:
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
