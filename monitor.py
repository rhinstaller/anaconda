#
# monitor.py - monitor probing and install data
#
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import kudzu
import iutil
import isys
from translate import _
from log import log

def isValidSyncRange(syncrange):

    def isValidPiece(piece):
        tmp = string.split(piece, "-")
        if len(tmp) > 2:
            return 0

        for i in tmp:
            try:
                tmp2 = float(i)
            except ValueError:
                return 0
            
        return 1

    pieces = string.split(syncrange, ",")
    for piece in pieces:
        if not isValidPiece(piece):
            return 0

    return 1



class MonitorInfo:

#
#  This class represents the monitor on the system. Values from ddcprobing
#  are provided if available.  LCDs are not currently probed.
#
#  Internal members (use methods to access):
#
#     monEisa     - probed monitor ID  (string)
#     monName     - human readable description (string)
#     monID       - human readable ID (string)
#     fbmonSect   - if framebuffer running, monitor ID (string)
#     monHoriz    - horizontal rating (kHz)
#     monVert     - vertical rating (Hz)
#
    def readMonitorsDB (self, lines = None):
        if self.monlist:
            return self.monlist
        if not lines:
            db = open ('/usr/X11R6/share/Xconfigurator/MonitorsDB')
            lines = db.readlines ()
            db.close ()

        for line in lines:
            line = string.strip (line)
            if not line:
                continue
            if line and line[0] == '#':
                continue
            fields = string.split (line, ';')
            man = string.strip(fields[0])
            model = string.strip(fields[1])
            eisa = string.lower(string.strip(fields[2]))
            horiz = string.strip(fields[3])
            vert = string.strip(fields[4])
            if self.monlist.has_key(man):
                self.monlist[man].append((model, eisa, vert, horiz))
            else:
                self.monlist[man] = [(model, eisa, vert, horiz)]
            self.monids[eisa] = (man, model, eisa, vert, horiz)
        return self.monlist

    def monitorsDB(self):
        if not self.monlist:
            self.readMonitorsDB()

        return self.monlist

    def monitorsEISADB(self):
        if not self.monlist:
            self.readMonitorsDB()

        return self.monids

    def lookupMonitor(self, monID):
        if not self.monlist:
            self.readMonitorsDB()

        for man in self.monlist.keys():
            for model in self.monlist[man]:
                if monID == model[0]:
                    return model

        return 0

    def __str__ (self):
        return  "monEisa: %s\nmonName: %s\nmonID: %s\nfbmonSect: %s\nmonHoriz: %s\nmonVert: %s\n" % (  self.monEisa, self.monName, self.monID, self.fbmonSect, self.monHoriz, self.monVert)

    def setSpecs(self, horiz, vert, id=None, name = None):
        self.monHoriz = horiz
        self.monVert = vert
        if id:
            self.monID = id
            
        if name:
            self.monName = name

    def getMonitorHorizSync(self, useProbed=0):
        if useProbed:
            return self.orig_monHoriz
        else:
            return self.monHoriz

    def getMonitorVertSync(self, useProbed=0):
        if useProbed:
            return self.orig_monVert
        else:
            return self.monVert

    def getFBMonitorSection(self):
        return self.fbmonSect

    def getFBMonitorMode(self):
        return self.fbmonMode

    def getMonitorID(self, useProbed = 0):
        if not useProbed:
            return self.monID
        else:
            return self.orig_monID

    def shortDescription(self):
        if self.monName and self.monName != "" and self.monName != "Unprobed Monitor":
            return self.monName
        else:
            return _("Unable to probe")
        

    def reset(self):
        self.monEisa = self.orig_monEisa
        self.monName = self.orig_monName
        self.monID = self.orig_monID
        self.fbmonSect = self.orig_fbmonSect
        self.monHoriz = self.orig_monHoriz
        self.monVert = self.orig_monVert

    def __init__ (self, skipDDCProbe = 0, fbDevice = None):

        self.monEisa = None
        self.monName = None
        self.monID = "Unprobed Monitor"

        self.fbmonSect = ""

        self.monHoriz = None
        self.monVert = None

        self.monlist = {}
        self.monids = {}

        # VESA probe for monitor/videoram, etc.
        if not skipDDCProbe:
	    try:
		probe = string.split (iutil.execWithCapture ("/usr/sbin/ddcprobe", ['ddcprobe']), '\n')
		for line in probe:
		    if line and line[:8] == "EISA ID:":
			self.monEisa = string.lower(line[9:])
			self.monID = line[9:]

		    if line and line[:6] == "\tName:":
			if not self.monName or len (self.monName) < len (line[7:]):
			    self.monName = line[7:]

		    if line and line[:15] == "\tTiming ranges:":
			ranges = string.split (line, ',')
			self.monHoriz = string.strip (string.split (ranges[0], '=')[1])
			self.monVert = string.strip (string.split (ranges[1], '=')[1])
                if self.monEisa:
                    # read the monitor DB
                    self.readMonitorsDB()
                    if self.monids.has_key (self.monEisa):
                        (man, model, eisa, vert, horiz) = self.monids[self.monEisa]
                        self.setSpecs(horiz, vert, id=model, name=model)
            except:
                log("ddcprobe failed")
                pass

        self.fbmonMode = {}
        if fbDevice != None:
            try:
                (vidram, depth, mode, monitor) = isys.fbconProbe("/dev/" + fbDevice)
                self.fbmonSect = monitor
                self.fbmonMode = {}
                self.fbmonMode[str(depth)] = [str(mode)]
            except:
                pass

        # save for reset() method
        self.orig_monEisa = self.monEisa
        self.orig_monName = self.monName
        self.orig_monID = self.monID

        self.orig_fbmonSect = self.fbmonSect

        self.orig_monHoriz = self.monHoriz
        self.orig_monVert = self.monVert
