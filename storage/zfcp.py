#
# zfcp.py - mainframe zfcp configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004  Red Hat, Inc.  All rights reserved.
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
# Author(s): Karsten Hopp <karsten@redhat.com>
#

import string
import os
from constants import *
from udev import udev_settle

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")
import warnings

def loggedWriteLineToFile(fn, value):
    f = open(fn, "w")
    log.debug("echo %s > %s" % (value, fn))
    f.write("%s\n" % (value))
    f.close()

zfcpsysfs = "/sys/bus/ccw/drivers/zfcp"
scsidevsysfs = "/sys/bus/scsi/devices"

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
        except TypeError:
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
        online = "%s/%s/online" %(zfcpsysfs, self.devnum)
        portadd = "%s/%s/port_add" %(zfcpsysfs, self.devnum)
        portdir = "%s/%s/%s" %(zfcpsysfs, self.devnum, self.wwpn)
        unitadd = "%s/unit_add" %(portdir)
        unitdir = "%s/%s" %(portdir, self.fcplun)
        failed = "%s/failed" %(unitdir)

        try:
            if not os.path.exists(online):
                loggedWriteLineToFile("/proc/cio_ignore",
                                      "free %s" %(self.devnum,))
                udev_settle()
        except IOError as e:
            raise ValueError, _("Could not free zFCP device %(devnum)s from "
                                "device ignore list (%(e)s).") \
                              % {'devnum': self.devnum, 'e': e}

        if not os.path.exists(online):
            raise ValueError, _(
                "zFCP device %s not found, not even in device ignore list."
                %(self.devnum,))

        try:
            f = open(online, "r")
            devonline = f.readline().strip()
            f.close()
            if devonline != "1":
                loggedWriteLineToFile(online, "1")
            else:
                log.info("zFCP device %s already online." %(self.devnum,))
        except IOError as e:
            raise ValueError, _("Could not set zFCP device %(devnum)s "
                                "online (%(e)s).") \
                              % {'devnum': self.devnum, 'e': e}

        if not os.path.exists(portdir):
            if os.path.exists(portadd):
                # older zfcp sysfs interface
                try:
                    loggedWriteLineToFile(portadd, self.wwpn)
                    udev_settle()
                except IOError as e:
                    raise ValueError, _("Could not add WWPN %(wwpn)s to zFCP "
                                        "device %(devnum)s (%(e)s).") \
                                      % {'wwpn': self.wwpn,
                                         'devnum': self.devnum,
                                         'e': e}
            else:
                # newer zfcp sysfs interface with auto port scan
                raise ValueError, _("WWPN %(wwpn)s not found at zFCP device "
                                    "%(devnum)s.") % {'wwpn': self.wwpn,
                                                      'devnum': self.devnum}
        else:
            if os.path.exists(portadd):
                # older zfcp sysfs interface
                log.info("WWPN %(wwpn)s at zFCP device %(devnum)s already "
                         "there.") % {'wwpn': self.wwpn,
                                      'devnum': self.devnum}

        if not os.path.exists(unitdir):
            try:
                loggedWriteLineToFile(unitadd, self.fcplun)
                udev_settle()
            except IOError as e:
                raise ValueError, _("Could not add LUN %(fcplun)s to WWPN "
                                    "%(wwpn)s on zFCP device %(devnum)s "
                                    "(%(e)s).") \
                                  % {'fcplun': self.fcplun, 'wwpn': self.wwpn,
                                     'devnum': self.devnum, 'e': e}
        else:
            raise ValueError, _("LUN %(fcplun)s at WWPN %(wwpn)s on zFCP "
                                "device %(devnum)s already configured.") \
                              % {'fcplun': self.fcplun,
                                 'wwpn': self.wwpn,
                                 'devnum': self.devnum}

        fail = "0"
        try:
            f = open(failed, "r")
            fail = f.readline().strip()
            f.close()
        except IOError as e:
            raise ValueError, _("Could not read failed attribute of LUN "
                                "%(fcplun)s at WWPN %(wwpn)s on zFCP device "
                                "%(devnum)s (%(e)s).") \
                              % {'fcplun': self.fcplun,
                                 'wwpn': self.wwpn,
                                 'devnum': self.devnum,
                                 'e': e}
        if fail != "0":
            self.offlineDevice()
            raise ValueError, _("Failed LUN %(fcplun)s at WWPN %(wwpn)s on "
                                "zFCP device %(devnum)s removed again.") \
                              % {'fcplun': self.fcplun,
                                 'wwpn': self.wwpn,
                                 'devnum': self.devnum}

        return True

    def offlineSCSIDevice(self):
        f = open("/proc/scsi/scsi", "r")
        lines = f.readlines()
        f.close()
        # alternatively iterate over /sys/bus/scsi/devices/*:0:*:*/

        for line in lines:
            if not line.startswith("Host"):
                continue
            scsihost = string.split(line)
            host = scsihost[1]
            channel = "0"
            id = scsihost[5]
            lun = scsihost[7]
            scsidev = "%s:%s:%s:%s" % (host[4:], channel, id, lun)
            fcpsysfs = "%s/%s" % (scsidevsysfs, scsidev)
            scsidel = "%s/%s/delete" % (scsidevsysfs, scsidev)

            f = open("%s/hba_id" %(fcpsysfs), "r")
            fcphbasysfs = f.readline().strip()
            f.close()
            f = open("%s/wwpn" %(fcpsysfs), "r")
            fcpwwpnsysfs = f.readline().strip()
            f.close()
            f = open("%s/fcp_lun" %(fcpsysfs), "r")
            fcplunsysfs = f.readline().strip()
            f.close()

            if fcphbasysfs == self.devnum \
                    and fcpwwpnsysfs == self.wwpn \
                    and fcplunsysfs == self.fcplun:
                loggedWriteLineToFile(scsidel, "1")
                udev_settle()
                return

        log.warn("no scsi device found to delete for zfcp %s %s %s"
                 %(self.devnum, self.wwpn, self.fcplun))

    def offlineDevice(self):
        offline = "%s/%s/online" %(zfcpsysfs, self.devnum)
        portadd = "%s/%s/port_add" %(zfcpsysfs, self.devnum)
        portremove = "%s/%s/port_remove" %(zfcpsysfs, self.devnum)
        unitremove = "%s/%s/%s/unit_remove" %(zfcpsysfs, self.devnum, self.wwpn)
        portdir = "%s/%s/%s" %(zfcpsysfs, self.devnum, self.wwpn)
        devdir = "%s/%s" %(zfcpsysfs, self.devnum)

        try:
            self.offlineSCSIDevice()
        except IOError as e:
            raise ValueError, _("Could not correctly delete SCSI device of "
                                "zFCP %(devnum)s %(wwpn)s %(fcplun)s "
                                "(%(e)s).") \
                              % {'devnum': self.devnum, 'wwpn': self.wwpn,
                                 'fcplun': self.fcplun, 'e': e}

        try:
            loggedWriteLineToFile(unitremove, self.fcplun)
        except IOError as e:
            raise ValueError, _("Could not remove LUN %(fcplun)s at WWPN "
                                "%(wwpn)s on zFCP device %(devnum)s "
                                "(%(e)s).") \
                              % {'fcplun': self.fcplun, 'wwpn': self.wwpn,
                                 'devnum': self.devnum, 'e': e}

        if os.path.exists(portadd):
            # only try to remove ports with older zfcp sysfs interface
            for lun in os.listdir(portdir):
                if lun.startswith("0x") and \
                        os.path.isdir(os.path.join(portdir, lun)):
                    log.info("Not removing WWPN %s at zFCP device %s since port still has other LUNs, e.g. %s."
                             %(self.wwpn, self.devnum, lun))
                    return True

            try:
                loggedWriteLineToFile(portremove, self.wwpn)
            except IOError as e:
                raise ValueError, _("Could not remove WWPN %(wwpn)s on zFCP "
                                    "device %(devnum)s (%(e)s).") \
                                  % {'wwpn': self.wwpn,
                                     'devnum': self.devnum, 'e': e}

        if os.path.exists(portadd):
            # older zfcp sysfs interface
            for port in os.listdir(devdir):
                if port.startswith("0x") and \
                        os.path.isdir(os.path.join(devdir, port)):
                    log.info("Not setting zFCP device %s offline since it still has other ports, e.g. %s."
                             %(self.devnum, port))
                    return True
        else:
            # newer zfcp sysfs interface with auto port scan
            import glob
            luns = glob.glob("%s/0x????????????????/0x????????????????"
                          %(devdir,))
            if len(luns) != 0:
                log.info("Not setting zFCP device %s offline since it still has other LUNs, e.g. %s."
                         %(self.devnum, luns[0]))
                return True

        try:
            loggedWriteLineToFile(offline, "0")
        except IOError as e:
            raise ValueError, _("Could not set zFCP device %(devnum)s "
                                "offline (%(e)s).") \
                              % {'devnum': self.devnum, 'e': e}

        return True

class ZFCP:
    """ ZFCP utility class.

        This class will automatically online to ZFCP drives configured in
        /tmp/fcpconfig when the startup() method gets called. It can also be
        used to manually configure ZFCP devices through the addFCP() method.

        As this class needs to make sure that /tmp/fcpconfig configured
        drives are only onlined once and as it keeps a global list of all ZFCP
        devices it is implemented as a Singleton.
    """

    def __init__(self):
        self.fcpdevs = []
        self.hasReadConfig = False
        self.down = True

    # So that users can write zfcp() to get the singleton instance
    def __call__(self):
        return self

    def readConfig(self):
        try:
            f = open("/tmp/fcpconfig", "r")
        except IOError:
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
                log.warn(str(e))
                continue

    def addFCP(self, devnum, wwpn, fcplun):
        d = ZFCPDevice(devnum, wwpn, fcplun)
        if d.onlineDevice():
            self.fcpdevs.append(d)

    def shutdown(self):
        if self.down:
            return
        self.down = True
        if len(self.fcpdevs) == 0:
            return
        for d in self.fcpdevs:
            try:
                d.offlineDevice()
            except ValueError, e:
                log.warn(str(e))

    def startup(self):
        if not self.down:
            return
        self.down = False
        if not self.hasReadConfig:
            self.readConfig()
            self.hasReadConfig = True
            # readConfig calls addFCP which calls onlineDevice already
            return
            
        if len(self.fcpdevs) == 0:
            return
        for d in self.fcpdevs:
            try:
                d.onlineDevice()
            except ValueError, e:
                log.warn(str(e))

    def writeKS(self, f):
        if len(self.fcpdevs) == 0:
            return
        for d in self.fcpdevs:
            f.write("zfcp --devnum %s --wwpn %s --fcplun %s\n" %(d.devnum,
                                                                 d.wwpn,
                                                                 d.fcplun))

    def write(self, instPath):
        if len(self.fcpdevs) == 0:
            return
        f = open(instPath + "/etc/zfcp.conf", "w")
        for d in self.fcpdevs:
            f.write("%s\n" %(d,))
        f.close()
        
        f = open(instPath + "/etc/modprobe.conf", "a")
        f.write("alias scsi_hostadapter zfcp\n")
        f.close()

# Create ZFCP singleton
ZFCP = ZFCP()

# vim:tw=78:ts=4:et:sw=4
