#
# dasd.py - DASD class
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
# Red Hat Author(s): David Cantrell <dcantrell@redhat.com>
#

import iutil
import sys
import os
from storage.devices import deviceNameToDiskByPath
from constants import *
from flags import flags

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

def getDasdPorts():
    """ Return comma delimited string of valid DASD ports. """
    ports = []

    f = open("/proc/dasd/devices", "r")
    lines = map(lambda x: x.strip(), f.readlines())
    f.close()

    for line in lines:
        if "unknown" in line:
            continue

        if "(FBA )" in line or "(ECKD)" in line:
            ports.append(line.split('(')[0])

    return ','.join(ports)

class DASD:
    """ Controlling class for DASD interaction before the storage code in
        anaconda has initialized.

        The DASD class can determine if any DASD devices on the system are
        unformatted and can perform a dasdfmt on them.
    """

    def __init__(self):
        self._dasdlist = []
        self._devices = []                  # list of DASDDevice objects
        self._totalCylinders = 0
        self._completedCylinders = 0.0
        self._maxFormatJobs = 0
        self.started = False

    def startup(self, *args, **kwargs):
        """ Look for any unformatted DASDs in the system and offer the user
            the option for format them with dasdfmt or exit the installer.
        """
        if self.started:
            return

        self.started = True

        if not iutil.isS390():
            return

        intf = kwargs.get("intf")
        zeroMbr = kwargs.get("zeroMbr")

        log.info("Checking for unformatted DASD devices:")

        for device in os.listdir("/sys/block"):
            if not device.startswith("dasd"):
                continue

            statusfile = "/sys/block/%s/device/status" % (device,)
            if not os.path.isfile(statusfile):
                continue

            f = open(statusfile, "r")
            status = f.read().strip()
            f.close()

            if status == "unformatted":
                log.info("    %s is an unformatted DASD" % (device,))
                self._dasdlist.append(device)

        if not len(self._dasdlist):
            log.info("    no unformatted DASD devices found")
            return

        askUser = True

        if zeroMbr:
            askUser = False
        elif not intf and not zeroMbr:
            log.info("    non-interactive kickstart install without zerombr "
                     "command, unable to run dasdfmt, exiting installer")
            sys.exit(0)

        tmplist = map(lambda s: "/dev/" + s, self._dasdlist)
        self._dasdlist = map(lambda s: deviceNameToDiskByPath(s), tmplist)
        c = len(self._dasdlist)

        if intf and askUser:
            title = P_("Unformatted DASD Device Found",
                       "Unformatted DASD Devices Found", c)
            msg = P_("Format uninitialized DASD device?\n\n"
                     "There is %d uninitialized DASD device on this "
                     "system.  To continue installation, the device must "
                     "be formatted.  Formatting will remove any data on "
                     "this device." % c,
                     "Format uninitialized DASD devices?\n\n"
                     "There are %d uninitialized DASD devices on this "
                     "system.  To continue installation, the devices must "
                     "be formatted.  Formatting will remove any data on "
                     "these devices." % c,
                     c)

            devs = ''
            for dasd in self._dasdlist:
                devs += "%s\n" % (dasd,)

            icon = "/usr/share/icons/gnome/32x32/status/dialog-error.png"
            buttons = [_("_Format"), _("_Exit installer")]
            rc = intf.detailedMessageWindow(title, msg, devs.strip(),
                                                 type="custom",
                                                 custom_icon=icon,
                                                 custom_buttons=buttons)
            if rc == 1:
                log.info("    not running dasdfmt, exiting installer")
                sys.exit(0)

        argv = ["-y", "-P", "-d", "cdl", "-b", "4096"]

        if intf:
            title = P_("Formatting DASD Device", "Formatting DASD Devices", c)
            msg = P_("Preparing %d DASD device for use with Linux..." % c,
                     "Preparing %d DASD devices for use with Linux..." % c, c)
            pw = intf.progressWindow(title, msg, 1.0)

            for dasd in self._dasdlist:
                log.info("Running dasdfmt on %s" % (dasd,))
                iutil.execWithCallback("/sbin/dasdfmt", argv + [dasd],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       callback=self._updateProgressWindow,
                                       callback_data=pw, echo=False)

            pw.pop()
        else:
            for dasd in self._dasdlist:
                log.info("Running dasdfmt on %s" % (dasd,))
                iutil.execWithRedirect("/sbin/dasdfmt", argv + [dasd],
                                       stdout="/dev/tty5", stderr="/dev/tty5")

    def addDASD(self, dasd):
        """ Adds a DASDDevice to the internal list of DASDs. """
        if dasd:
            self._devices.append(dasd)

    def write(self, instPath):
        """ Write /etc/dasd.conf to target system for all DASD devices
            configured during installation.
        """
        if self._devices == []:
            return

        f = open(os.path.realpath(instPath + "/etc/dasd.conf"), "w")
        for dasd in self._devices:
            fields = [dasd.busid] + dasd.getOpts()
            f.write("%s\n" % (" ".join(fields),))
        f.close()

    def _updateProgressWindow(self, data, callback_data=None):
        """ Reads progress output from dasdfmt and collects the number of
            cylinders completed so the progress window can update.
        """
        if not callback_data:
            return

        if data == '\n':
            # each newline we see in this output means one more cylinder done
            self._completedCylinders += 1.0
            callback_data.set(self._completedCylinders / self.totalCylinders)

    @property
    def totalCylinders(self):
        """ Total number of cylinders of all unformatted DASD devices. """
        if self._totalCylinders:
            return self._totalCylinders

        argv = ["-t", "-v", "-y", "-d", "cdl", "-b", "4096"]
        for dasd in self._dasdlist:
            buf = iutil.execWithCapture("/sbin/dasdfmt", argv + [dasd],
                                        stderr="/dev/tty5")
            for line in buf.splitlines():
                if line.startswith("Drive Geometry: "):
                    # line will look like this:
                    # Drive Geometry: 3339 Cylinders * 15 Heads =  50085 Tracks
                    cyls = long(filter(lambda s: s, line.split(' '))[2])
                    self._totalCylinders += cyls
                    break

        return self._totalCylinders

# vim:tw=78:ts=4:et:sw=4
