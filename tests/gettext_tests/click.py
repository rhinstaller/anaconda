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
import sys

# Something like looks more or less like an <a> tag
link_re = re.compile(r'<\s*a(\s|>)')

# Something that looks like a clickable message
click_re = re.compile(r'\b[Cc]lick for\b')

# Strings to ignore
ignore_msgs = ['Click for help.']

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

# Parse anaconda.pot and rearrange the POFile object into a dict of {msgid: POEntry}
pofile = polib.pofile(os.environ['top_builddir'] + "/po/anaconda.pot")
msgs = {e.msgid: e for e in pofile}

success = True
for msg in msgs.keys():
    if msg in ignore_msgs:
        continue

    # Remove underscores to avoid trouble with underline-based accelerators
    trimmed_msg = msg.replace('_', '')

    # Look for claims of clickability
    if click_re.search(trimmed_msg):
        # Look for something to click
        if not link_re.search(trimmed_msg):
            print("String at %s appears to be clickable but has nothing to click." %
                    " ".join("%s:%s" % (o[0], o[1]) for o in msgs[msg].occurrences))
            success = False

sys.exit(0 if success else 1)
