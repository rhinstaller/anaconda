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

from rhpl.translate import _, N_
from rhpl.log import log


class ZFCP:
    def __init__(self):
        self.readConfig()

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
                log("echo %s > %s" % (0, fno))
                fo.write("0")
                fo.close()
                try:
                    fu = open(fnu, "w")
                    log("echo %s > %s" % (fcpdevices[i][4], fnu))
                    fu.write("%s\n" % (fcpdevices[i][4],))
                    fu.close()
                    try:
                        fp = open(fnp, "w")
                        log("echo %s > %s" % (fcpdevices[i][2], fnp))
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
               log("echo %s > %s" % (fcpdevices[i][2], fnp))
               fp.write("%s\n" % (fcpdevices[i][2],))
               fp.close()
               try:
                  fu = open(fnu, "w")
                  log("echo %s > %s" % (fcpdevices[i][4], fnu))
                  fu.write("%s\n" % (fcpdevices[i][4],))
                  fu.close()
                  try:
                     fo = open(fno, "w")
                     log("echo %s > %s" % (1, fno))
                     fo.write("1")
                     fo.close()
                  except:
                     log("opening %s failed" %(fno,))
                     continue
               except:
                  log("opening %s failed" %(fnu,))
                  continue
            except:
               log("opening %s failed" %(fnp,))
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

    def write(self, instPath):
        if not len(self.fcpdevices):
            return
        if not os.path.isdir("%s/etc/" %(instPath,)):
            iutil.mkdirChain("%s/etc/" %(instPath,))

        fn = "%s/etc/zfcp.conf" % (instPath,)
        f = open(fn, "w")
        os.chmod(fn, 0644)
        for dev in self.fcpdevices:
            f.write("%s %s %s %s %s\n" % (dev[0], dev[1], dev[2], dev[3], dev[4],))
        f.close()

    def writeKS(self,fcpdevices):
        # FIXME KH not implemented yet
        return

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
                line = string.lower(string.strip(line))
                fcpconf = string.split(line)
                if len(line) > 0  and (len(fcpconf) != 5 or fcpconf[0][:1] == "#"):   # nonempty but invalid line or comment
                    continue
                for i in range(1,5):
                    if fcpconf[i][:2] != "0x":
                        fcpconf[i] = "0x" + fcpconf[i]
                fcpconf[4] = self.expandLun(fcpconf[4])
                self.fcpdevices.append(fcpconf)

    def sanityCheckHexValue(self, length, value):
        # FIXME: do a real checking if this is a valid hex value
        if len(value) == length:
            return None
        else:
            return _("Invalid input. Entered string must have %d characters") % length

    # ZFCP LUNs are usually entered as 16 bit, sysfs accepts only 64 bit 
    # (#125632), expand with zeroes if necessary
    def expandLun(self, lun):
        if lun[:2] == "0x":
            lun = lun[2:]
        lun = "0x" + "0" * (4 - len(lun)) + lun
        lun = lun + "0" * (16 - len(lun) + 2)
        return lun


# vim:tw=78:ts=4:et:sw=4
