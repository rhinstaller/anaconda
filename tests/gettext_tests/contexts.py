#!/usr/bin/python3
#
# Copyright (C) 2015  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import string  # pylint: disable=deprecated-module
import sys


def list_occurrences(occurrences):
    # Return polib's occurrences list [('file1', line1), ('file2', line2), ...]
    # as a space-separated list of file1:line1 etc.
    return " ".join("%s:%s" % (o[0], o[1]) for o in occurrences)

def is_accelerated(message):
    # True if there is a _ anywhere outside of a format parameter name
    if "_" not in message.msgid:
        return False

    if "python-format" in message.flags:
        # This is a %-formatted string: strip out everything from %
        # to the end of a word, or at least to the end of the identifier
        # we're trying to ignore
        if "_" not in re.sub('%[()_a-zA-Z0-9]*', '', message.msgid):
            return False

    elif "python-brace-format" in message.flags:
        # This is a PEP 3101 format string: use a Formatter object to
        # strip out all of the format bits. The first part of each tuple
        # returned by parse is the literal portion of the string.
        formatter = string.Formatter()
        literal = ''.join(s[0] for s in formatter.parse(message.msgid))
        if "_" not in literal:
            return False

    return True

# Use polib to parse anaconda.pot
try:
    import polib
except ImportError:
    print("You need to install the python-polib package to read anaconda.pot")
    # This return code tells the automake test driver that the test setup failed
    sys.exit(99)

if "top_srcdir" not in os.environ:
    sys.stderr.write("$top_srcdir must be defined in the test environment\n")
    sys.exit(99)

if "top_builddir" not in os.environ:
    sys.stderr.write("$top_srcdir must be defined in the test environment\n")
    sys.exit(99)

# Parse anaconda.pot
pofile = polib.pofile(os.environ['top_builddir'] + "/po/anaconda.pot")

success = True

# There are two cases that require contexts: GUI strings with keyboard accelerators,
# and single-character TUI strings (e.g. c for continue)

# First, the GUI strings with accelerators
for msg in (p for p in pofile if is_accelerated(p)):
    if not msg.msgctxt:
        print("Keyboard accelerator missing context at %s" % list_occurrences(msg.occurrences))
        success = False

# Next, the abbreviations. These strings also require a comment to explain what
# they are abbreviating.
for msg in (p for p in pofile if len(p.msgid) == 1):
    if not msg.msgctxt:
        print("Abbreviation %s is missing context at %s" %
                (msg.msgid, list_occurrences(msg.occurrences)))
        success = False

    if not msg.comment:
        print("Abbreviation %s is missing a comment at %s" %
                (msg.msgid, list_occurrences(msg.occurrences)))

sys.exit(0 if success else 1)
