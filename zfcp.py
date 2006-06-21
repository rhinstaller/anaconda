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

class ZFCP:
    def __init__(self):
        self.description = _("zSeries machines can access industry-standard SCSI devices via Fibre Channel (FCP). You need to provide 5 parameters for each device: a 16 bit device number, a 16bit SCSI ID, a 64 bit World Wide Port Name (WWPN), a 16bit SCSI LUN and a 64 bit FCP LUN.")
        self.options = [
            (_("Device number"), 1,
             _("You have not specified a device number or the number is invalid"),
             self.sanitizeDeviceInput, self.checkValidDevice),
            (_("SCSI Id"), 0,
             _("You have not specified a SCSI ID or the ID is invalid."),
             self.sanitizeHexInput, self.checkValidID),
            (_("WWPN"), 1,
             _("You have not specified a worldwide port name or the name is invalid."),
             self.sanitizeHexInput, self.checkValid64BitHex),
            (_("SCSI LUN"), 0,
             _("You have not specified a SCSI LUN or the number is invalid."),
             self.sanitizeHexInput, self.checkValidID),
            (_("FCP LUN"), 1,
             _("You have not specified a FCP LUN or the number is invalid."),
             self.sanitizeFCPLInput, self.checkValid64BitHex)]
        self.readConfig()

    def hextest(self, hex):
        try:
            int(hex, 16)
            return 0
        except:
            return -1

    def checkValidDevice(self, id):
        if id is None or id == "":
            return -1
        if len(id) != 8:             # p.e. 0.0.0600
            return -1
        if id[0] not in string.digits or id[2] not in string.digits:
            return -1
        if id[1] != "." or id[3] != ".":
            return -1
        return self.hextest(id[4:])

    def checkValidID(self, hex):
        if hex is None or hex == "":
            return -1
        if len(hex) > 6:
            return -1
        return self.hextest(hex)

    def checkValid64BitHex(self, hex):
        if hex is None or hex == "":
            return -1
        if len(hex) != 18:
            return -1
        return self.hextest(hex)

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

    def sanitizeHexInput(self, id):
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


    def updateConfig(self, fcpdevices, diskset, intf):
        self.writeFcpSysfs(fcpdevices)
        self.writeModprobeConf(fcpdevices)
        self.writeZFCPconf(fcpdevices)
        isys.flushDriveDict()
        diskset.refreshDevices(intf)
        try:
            iutil.makeDriveDeviceNodes()
        except:
            pass

    # remove the configuration from sysfs, required when the user
    # steps backward from the partitioning screen and changes fcp configuration
    def cleanFcpSysfs(self, fcpdevices):
        if not len(fcpdevices):
            return
        on = "/sys/bus/ccw/drivers/zfcp/%s/online"
        pr = "/sys/bus/ccw/drivers/zfcp/%s/port_remove"
        ur = "/sys/bus/ccw/drivers/zfcp/%s/%s/unit_remove"
        for i in range(len(fcpdevices)):
            fno = on % (fcpdevices[i][0],)
            fnp = pr % (fcpdevices[i][0],)
            fnu = ur % (fcpdevices[i][0],fcpdevices[i][2],)
            try:
                fo = open(fno, "w")
                log.info("echo %s > %s" % (0, fno))
                fo.write("0")
                fo.close()
                try:
                    fu = open(fnu, "w")
                    log.info("echo %s > %s" % (fcpdevices[i][4], fnu))
                    fu.write("%s\n" % (fcpdevices[i][4],))
                    fu.close()
                    try:
                        fp = open(fnp, "w")
                        log.info("echo %s > %s" % (fcpdevices[i][2], fnp))
                        fp.write("%s\n" % (fcpdevices[i][2],))
                        fp.close()
                    except:
                        continue
                except:
                    continue
            except:
                continue

    # initialize devices via sysfs
    def writeFcpSysfs(self,fcpdevices):
        if not len(fcpdevices):
            return
        on = "/sys/bus/ccw/drivers/zfcp/%s/online"
        pa = "/sys/bus/ccw/drivers/zfcp/%s/port_add"
        ua = "/sys/bus/ccw/drivers/zfcp/%s/%s/unit_add"
        for i in range(len(fcpdevices)):
            fno = on % (fcpdevices[i][0],)
            fnp = pa % (fcpdevices[i][0],)
            fnu = ua % (fcpdevices[i][0],fcpdevices[i][2],)
            try:
               fp = open(fnp, "w")
               log.info("echo %s > %s" % (fcpdevices[i][2], fnp))
               fp.write("%s\n" % (fcpdevices[i][2],))
               fp.close()
               try:
                  fu = open(fnu, "w")
                  log.info("echo %s > %s" % (fcpdevices[i][4], fnu))
                  fu.write("%s\n" % (fcpdevices[i][4],))
                  fu.close()
                  try:
                     fo = open(fno, "w")
                     log.info("echo %s > %s" % (1, fno))
                     fo.write("1")
                     fo.close()
                  except:
                     log.warning("opening %s failed" %(fno,))
                     continue
               except:
                  log.warning("opening %s failed" %(fnu,))
                  continue
            except:
               log.warning("opening %s failed" %(fnp,))
               continue

    def writeModprobeConf(self, fcpdevices):
        lines = []
        try:
            f = open("/tmp/modprobe.conf", "r")
            lines = f.readlines()
            f.close()
        except:
            pass
        foundalias = 0
        for line in lines:
            if string.find(string.strip(line), "alias scsi_hostadapter zfcp") == 0:
                foundalias = 1
                break
        if len(fcpdevices):
            if not foundalias:
                try:
                    f = open("/tmp/modprobe.conf", "a")
                    f.write("alias scsi_hostadapter zfcp\n")
                    f.close()
                except:
                    pass
        if not len(fcpdevices):
            if foundalias:
                try:
                    f = open("/tmp/modprobe.conf", "w")
                    for line in lines:
                        if string.find(string.strip(line), "alias scsi_hostadapter zfcp") != 0:
                            f.write(line)
                    f.close()
                except:
                    pass

    def writeZFCPconf(self, fcpdevices):
        if not len(fcpdevices):
            return
        f = open("/tmp/zfcp.conf", "w")
        for dev in fcpdevices:
            f.write("%s %s %s %s %s\n" % (dev[0], dev[1], dev[2], dev[3], dev[4],))
        f.close()

    def writeKS(self,fcpdevices):
        # FIXME KH not implemented yet
        return

    def write(self, instPath):
        if os.path.exists("/tmp/zfcp.conf"):
            shutil.copyfile("/tmp/zfcp.conf", instPath + "/etc/zfcp.conf")

    def readConfig(self):
        self.fcpdevices = []
        try:
            f = open("/tmp/fcpconfig", "r")
        except:
            pass
        else:
            lines = f.readlines()
            f.close()
            for line in lines:
                invalid = 0
                line = string.strip(line).lower()
                fcpconf = string.split(line)
                if len(fcpconf) != 5 or fcpconf[0][:1] == "#":
                    continue
                for i in range(len(self.options)):
                    fcpconf[i] = self.options[i][3](fcpconf[i])
                    if self.options[i][4](fcpconf[i]) == -1:
                        invalid = 1
                        break
                if not invalid:
                    self.fcpdevices.append(fcpconf)


# vim:tw=78:ts=4:et:sw=4
