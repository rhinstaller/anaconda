#!/usr/bin/python3
#
# Copyright (C) 2014  Red Hat, Inc.
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

# {'bad re': 'suggestion'}
# (?i) makes the re case-insensitive
bad_strings = {'(?i)bootloader': 'boot loader',
               '(?i)filesystem': 'file system',
               '(?i)username':   'user name',
               '[Vv]lan':        'VLAN',
               '(?i)hostname':   'host name',
               'ZFCP':           'zFCP',
               'zfcp':           'zFCP',
               'BTRFS':          'Btrfs',
               'btrfs':          'Btrfs',
               '[Cc]an not':     'cannot',
               '(?i)mountpoint': 'mount point',
               'Ok':             'OK',
               '(?i)os tree ':   'OSTree',
               # Find instances of "return" that are referring to a keyboard key
               '(?i)<return>':   '[Enter]',
               '(?i)press return': 'press Enter',
               # Make sure "Enter" is capitalized
               '<enter>':        '[Enter]',
               '[Pp]ress enter': 'press Enter'
               }

# Sometimes we need to use a bad string, or it's just too much of a pain to
# write a more specific regex. List occurrences here.
# {'filename': {'matched string', occurrences}}
expected_badness = {
    'pyanaconda/modules/storage/bootloader/base.py': {
        'mountpoint': 1,  # format string specifier
        'bootloader': 1,  # format string specifier
    },
    'pyanaconda/modules/storage/partitioning/custom/custom_partitioning.py': {
        'btrfs': 1        # quoted filesystem type
    },
    'pyanaconda/network.py': {
        'vlan': 1,        # format string specifier
    },
    'pyanaconda/rescue.py': {
        'mountpoint': 1,  # format string specifier
    },
    'pyanaconda/startup_utils.py': {
        'HOSTNAME': 1,    # ssh to install@HOSTNAME
    },
    'pyanaconda/modules/storage/devicetree/fsset.py': {
        'mountpoint': 1,  # format string specifier mount_point
    },
    'pyanaconda/ui/gui/spokes/subscription.glade': {
       'hostname': 1      # hostname:port placeholder for proxy URL entry
    }
}

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
    sys.stderr.write("$top_builddir must be defined in the test environment\n")
    sys.exit(99)

# Parse anaconda.pot and rearrange the POFile object into a dict of {msgid: POEntry}
pofile = polib.pofile(os.environ['top_builddir'] + "/po/anaconda.pot")
msgs = {e.msgid: e for e in pofile}

# Look for each of the bad regexes
success = True
for badre, suggestion in bad_strings.items():
    regex = re.compile(badre)
    for msg, msg_data in msgs.items():
        match = re.search(regex, msg.replace('_', ''))
        if match:
            # If this is something expected, decrement the occurrence count in expected_badness
            badstr = match.group(0)
            remainder = []
            for occur in msg_data.occurrences:
                if occur[0] in expected_badness and badstr in expected_badness[occur[0]]:
                    expected_badness[occur[0]][badstr] -= 1
                    if expected_badness[occur[0]][badstr] == 0:
                        del expected_badness[occur[0]][badstr]
                    if not expected_badness[occur[0]]:
                        del expected_badness[occur[0]]
                else:
                    remainder.append(occur)

            if remainder:
                print("Bad string %(bad)s found at %(occurrences)s. Try %(suggestion)s instead." %
                      {"bad": badstr,
                       "occurrences": " ".join(("%s:%s" % (o[0], o[1]) for o in remainder)),
                       "suggestion": suggestion})
                success = False

if expected_badness:
    for filename, badness_file in expected_badness.items():
        for badstr, badness_nmr in badness_file.items():
            print("Did not find %d occurrences of %s in %s" %
                    (badness_nmr, badstr, filename))
    success = False

sys.exit(0 if success else 1)
