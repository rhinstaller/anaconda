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

    def lookupMonitorByID(self, monID):
        if not self.monlist:
            self.readMonitorsDB()

        for man in self.monlist.keys():
            for model in self.monlist[man]:
		idlower = string.lower(monID)
		idupper = string.upper(monID)
                if idlower == model[1] or idupper == model[1]:
                    return model

        return 0

    def lookupMonitorByName(self, monName):
        if not self.monlist:
            self.readMonitorsDB()

        for man in self.monlist.keys():
            for model in self.monlist[man]:
		if monName == model[0]:
                    return model

        return None


    def __str__ (self):
        return  "monName: %s\nmonID: %s\nfbmonSect: %s\nmonHoriz: %s\nmonVert: %s\n" % ( self.monName, self.monID, self.fbmonSect, self.monHoriz, self.monVert)

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
	    if self.orig_use_probed:
		return self.probedMonitor[0]
	    else:
		return self.monID

    def getMonitorName(self):
	return self.monName

    def shortDescription(self):
        if self.monName and self.monName != "" and self.monName != "Unprobed Monitor":
            return self.monName
        else:
            return _("Unable to probe")

    def getDDCProbeResults(self):
	if self.orig_use_probed:
	    return self.probedMonitor
	else:
	    return None

    def reset(self):
        self.monName = self.orig_monName
        self.monID = self.orig_monID
        self.fbmonSect = self.orig_fbmonSect
        self.monHoriz = self.orig_monHoriz
        self.monVert = self.orig_monVert

    def __init__ (self, skipDDCProbe = 0, fbDevice = None):

        self.monName = None
        self.monID = "Unprobed Monitor"

        self.fbmonSect = ""

        self.monHoriz = None
        self.monVert = None

        self.monlist = {}
        self.monids = {}

	# store probed values for future reference
	self.probedMonitor = []

	# flag if the original monitor was probed or not
	self.orig_use_probed = 0
	
        # VESA probe for monitor/videoram, etc.
        if not skipDDCProbe:
	    try:
                monitor = kudzu.probe(kudzu.CLASS_MONITOR, kudzu.BUS_DDC,
                                      kudzu.PROBE_ALL)

		monEisa = None
		monName = None
		monHoriz = None
		monVert = None
		
                if monitor:
		    self.orig_use_probed = 1
                    monEisa = monitor[0].id

                    # only guess the timings if something is non-zero
                    if (monitor[0].horizSyncMin != 0 or
                        monitor[0].horizSyncMax != 0 or
                        monitor[0].vertRefreshMin != 0 or
                        monitor[0].vertRefreshMax != 0):
                        monHoriz = "%d-%d" % (monitor[0].horizSyncMin,
                                                   monitor[0].horizSyncMax)
                        monVert = "%d-%d" % (monitor[0].vertRefreshMin,
                                                  monitor[0].vertRefreshMax)
		    if monitor[0].desc != None:
			monName = monitor[0].desc

		    self.probedMonitor = (monEisa, monName, monHoriz, monVert)
		    self.setSpecs(monHoriz, monVert, id="DDCPROBED", name=monName)
            except:
                log("ddcprobe failed")
                pass

        self.fbmonMode = {}
        if fbDevice != None:
            try:
                (vidram, depth, mode, monitor) = isys.fbconProbe("/dev/" + fbDevice)
                self.fbmonSect = monitor
                self.fbmonMode = {}
                if int(depth) == 24:
                    depth = 32
                
                self.fbmonMode[str(depth)] = [str(mode)]
            except:
                pass

        # save for reset() method
        self.orig_monName = self.monName
        self.orig_monID = self.monID

        self.orig_fbmonSect = self.fbmonSect

        self.orig_monHoriz = self.monHoriz
        self.orig_monVert = self.monVert
