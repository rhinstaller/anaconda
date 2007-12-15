#
# timezone.py - timezone install data
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import shutil
import iutil
from flags import flags

import logging
log = logging.getLogger("anaconda")

def bool(val):
    if val: return "true"
    return "false"

class Timezone:

    def writeKS(self, f):
	f.write("timezone")
	if self.utc:
	    f.write(" --utc")
	f.write(" %s\n" % self.tz)

    def write(self, instPath):
	# dont do this in test mode!
	if flags.test:
	    return
	
	fromFile = instPath + "/usr/share/zoneinfo/" + self.tz

	try:
	    shutil.copyfile(fromFile, instPath + "/etc/localtime")
	except OSError, (errno, msg):
	    log.error("Error copying timezone (from %s): %s" % (fromFile, msg))

	f = open(instPath + "/etc/sysconfig/clock", "w")

	f.write('ZONE="%s"\n' % self.tz)
	f.write("UTC=%s\n" % bool(self.utc))
	f.write("ARC=%s\n" % bool(self.arc))

	f.close()

    def getTimezoneInfo(self):
	return (self.tz, self.utc, self.arc)

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.tz = timezone
	self.utc = asUtc
	self.arc = asArc

    def __init__(self):
	self.tz = "America/New_York"
	self.utc = 0
	self.arc = 0
