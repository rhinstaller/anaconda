#
# zfcp.py - mainframe zfcp configuration install data
#
# Karsten Hopp <karsten@redhat.com>
#
# Copyright 2001-2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import os
import iutil
import isys
import shutil

from rhpl.translate import _, N_

import logging
log = logging.getLogger("anaconda")
import warnings

def loggedWriteLineToFile(fn, value):
    f = open(fn, "w")
    log.debug("echo %s > %s" % (value, fn))
    f.write("%s\n" % (value))
    f.close()

zfcpsysfs = "/sys/bus/ccw/drivers/zfcp"

class ZFCPDevice:
    def __init__(self, devnum, wwpn, fcplun):
        self.devnum = self.sanitizeDeviceInput(devnum)
        self.wwpn = self.sanitizeWWPNInput(wwpn)
        self.fcplun = self.sanitizeFCPLInput(fcplun)

        if not self.checkValidDevice(self.devnum):
            raise ValueError, _("You have not specified a device number or the number is invalid")
        if not self.checkValidWWPN(self.wwpn):
            raise ValueError, _("You have not specified a worldwide port name or the name is invalid.")
        if not self.checkValidFCPLun(self.fcplun):
            raise ValueError, _("You have not specified a FCP LUN or the number is invalid.")

        self.onlineStatus = False

    def __str__(self):
        return "%s %s %s" %(self.devnum, self.wwpn, self.fcplun)

    def sanitizeDeviceInput(self, dev):
        if dev is None or dev == "":
            return None
        dev = dev.lower()
        bus = dev[:string.rfind(dev, ".") + 1]
        dev = dev[string.rfind(dev, ".") + 1:]
        dev = "0" * (4 - len(dev)) + dev
        if not len(bus):
            return "0.0." + dev
        else:
            return bus + dev

    def sanitizeWWPNInput(self, id):
        if id is None or id == "":
            return None
        id = id.lower()
        if id[:2] != "0x":
            return "0x" + id
        return id

    # ZFCP LUNs are usually entered as 16 bit, sysfs accepts only 64 bit 
    # (#125632), expand with zeroes if necessary
    def sanitizeFCPLInput(self, lun):
        if lun is None or lun == "":
            return None
        lun = lun.lower()
        if lun[:2] == "0x":
            lun = lun[2:]
        lun = "0x" + "0" * (4 - len(lun)) + lun
        lun = lun + "0" * (16 - len(lun) + 2)
        return lun

    def _hextest(self, hex):
        try:
            int(hex, 16)
            return True
        except:
            return False

    def checkValidDevice(self, id):
        if id is None or id == "":
            return False
        if len(id) != 8:             # p.e. 0.0.0600
            return False
        if id[0] not in string.digits or id[2] not in string.digits:
            return False
        if id[1] != "." or id[3] != ".":
            return False
        return self._hextest(id[4:])

    def checkValid64BitHex(self, hex):
        if hex is None or hex == "":
            return False
        if len(hex) != 18:
            return False
        return self._hextest(hex)
    checkValidWWPN = checkValidFCPLun = checkValid64BitHex

    def onlineDevice(self):
        if self.onlineStatus:
            return True
        
        online = "%s/%s/online" %(zfcpsysfs, self.devnum)
        portadd = "%s/%s/port_add" %(zfcpsysfs, self.devnum)
        unitadd = "%s/%s/%s/unit_add" %(zfcpsysfs, self.devnum, self.wwpn)
        try:
            if not os.path.exists(unitadd):
                loggedWriteLineToFile(portadd, self.wwpn)

            loggedWriteLineToFile(unitadd, self.fcplun)
            loggedWriteLineToFile(online, "1")
        except Exception, e:
            log.warn("error bringing zfcp device %s online: %s"
                     %(self.devnum, e))
            return False

        self.onlineStatus = True
        return True

    def offlineDevice(self):
        if not self.offlineStatus:
            return True
        
        offline = "%s/%s/offline" %(zfcpsysfs, self.devnum)
        portremove = "%s/%s/port_remove" %(zfcpsysfs, self.devnum)
        unitremove = "%s/%s/%s/unit_remove" %(zfcpsysfs, self.devnum, self.wwpn)
        try:
            loggedWriteLineToFile(offline, "0")
            loggedWriteLineToFile(unitremove, self.fcplun)
            loggedWriteLineToFile(portremove, self.wwpn)
        except Exception, e:
            log.warn("error bringing zfcp device %s offline: %s"
                     %(self.devnum, e))
            return False

        self.onlineStatus = False
        return True

class ZFCP:
    def __init__(self):
        self.fcpdevs = []
        self.readConfig()

    def readConfig(self):
        try:
            f = open("/tmp/fcpconfig", "r")
        except:
            log.info("no /tmp/fcpconfig; not configuring zfcp")
            return

        lines = f.readlines()
        f.close()
        for line in lines:
            # each line is a string separated list of values to describe a dev
            # there are two valid formats for the line:
            #   devnum scsiid wwpn scsilun fcplun    (scsiid + scsilun ignored)
            #   devnum wwpn fcplun
            line = string.strip(line).lower()
            if line.startswith("#"):
                continue
            fcpconf = string.split(line)
            if len(fcpconf) == 3:
                devnum = fcpconf[0]
                wwpn = fcpconf[1]
                fcplun = fcpconf[2]
            elif len(fcpconf) == 5:
                warnings.warn("SCSI ID and SCSI LUN values for ZFCP devices are ignored and deprecated.", DeprecationWarning)
                devnum = fcpconf[0]
                wwpn = fcpconf[2]
                fcplun = fcpconf[4]
            else:
                log.warn("Invalid line found in /tmp/fcpconfig!")
                continue

            try:
                self.addFCP(devnum, wwpn, fcplun)
            except ValueError, e:
                log.warn("Invalid FCP device configuration: %s" %(e,))
                continue

    def addFCP(self, devnum, wwpn, fcplun):
        d = ZFCPDevice(devnum, wwpn, fcplun)
        if d.onlineDevice():
            self.fcpdevs.append(d)
            f = open("/tmp/zfcp.conf", "a")
            f.write("%s\n" %(d,))
            f.close()

    def shutdown(self):
        if len(self.fcpdevs) == 0:
            return
        for d in self.fcpdevs:
            d.offlineDevice()
        # empty zfcp.conf as we'll write things back out when we initialize
        f = open("/tmp/zfcp.conf", "w+")
        f.close()

    def startup(self):
        if len(self.fcpdevs) == 0:
            return
        for d in self.fcpdevs:
            if d.onlineDevice():
                f = open("/tmp/zfcp.conf", "a")
                f.write("%s\n" %(d,))
                f.close()

    def writeKS(self,fcpdevices):
        # FIXME KH not implemented yet
        return

    def write(self, instPath):
        if len(self.fcpdevs) == 0:
            return
        if os.path.exists("/tmp/zfcp.conf"):
            shutil.copyfile("/tmp/zfcp.conf", instPath + "/etc/zfcp.conf")

# vim:tw=78:ts=4:et:sw=4
