#!/usr/bin/python
#
# dumphdrlist.py - dump the header list and give the discs that each
# package is on
#
# Copyright 2002 Red Hat, Inc.
# Author: Jeremy Katz <katzj@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import rpm
import os
import sys

def usage():
    print "%s <headerlist>" % (sys.argv[0])

def compareHeaders(first, second):
    name1 = first[rpm.RPMTAG_NAME]
    name2 = second[rpm.RPMTAG_NAME]

    if (name1 < name2):
        return -1
    elif (name1 > name2):
        return 1
    return 0


if len(sys.argv) < 2:
    usage()
    sys.exit(0)

hdlist = rpm.readHeaderListFromFile(sys.argv[1])
hdlist.sort(compareHeaders)
for hdr in hdlist:
    if hdr[rpm.RPMTAG_EPOCH] == None:
        epoch = "0"
    else:
        epoch = hdr[rpm.RPMTAG_EPOCH]
    print "%s:%s-%s-%s.%s %s %s" %(epoch,
                                hdr[rpm.RPMTAG_NAME], hdr[rpm.RPMTAG_VERSION],
                                hdr[rpm.RPMTAG_RELEASE], hdr[rpm.RPMTAG_ARCH],
                                hdr[1000002], hdr[1000003])
    
