#
# dasd.py - DASD class
#
# Copyright (C) 2009, 2010  Red Hat, Inc.  All rights reserved.
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

from pyanaconda import iutil
import sys
import os
from pyanaconda.storage.errors import DasdFormatError
from pyanaconda.storage.devices import deviceNameToDiskByPath
from pyanaconda.constants import *
from pyanaconda.flags import flags
from pyanaconda.baseudev import udev_trigger

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
        self.totalCylinders = 0
        self._completedCylinders = 0.0
        self._maxFormatJobs = 0
        self.dasdfmt = "/sbin/dasdfmt"
        self.commonArgv = ["-y", "-d", "cdl", "-b", "4096"]
        self.started = False

    def __call__(self):
        return self

    def startup(self, intf, exclusiveDisks, zeroMbr):
        """ Look for any unformatted DASDs in the system and offer the user
            the option for format them with dasdfmt or exit the installer.
        """
        if self.started:
            return

        self.started = True
        out = "/dev/tty5"
        err = "/dev/tty5"

        if not iutil.isS390():
            return

        # Trigger udev data about the dasd devices on the system
        udev_trigger(action="change", name="dasd*")

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

            if status in ["unformatted"] and device not in exclusiveDisks:
                bypath = deviceNameToDiskByPath(device)
                if not bypath:
                    bypath = "/dev/" + device

                log.info("    %s (%s) status is %s, needs dasdfmt" % (device,
                                                                      bypath,
                                                                      status,))
                self._dasdlist.append((device, bypath))

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

        c = len(self._dasdlist)

        if intf and askUser:
            devs = ''
            for dasd, bypath in self._dasdlist:
                devs += "%s\n" % (bypath,)

            rc = intf.questionInitializeDASD(c, devs)
            if rc == 1:
                log.info("    not running dasdfmt, continuing installation")
                return

        # gather total cylinder count
        argv = ["-t", "-v"] + self.commonArgv
        for dasd, bypath in self._dasdlist:
            buf = iutil.execWithCapture(self.dasdfmt, argv + ["/dev/" + dasd],
                                        stderr=err)
            for line in buf.splitlines():
                if line.startswith("Drive Geometry: "):
                    # line will look like this:
                    # Drive Geometry: 3339 Cylinders * 15 Heads =  50085 Tracks
                    cyls = long(filter(lambda s: s, line.split(' '))[2])
                    self.totalCylinders += cyls
                    break

        # format DASDs
        argv = ["-P"] + self.commonArgv
        update = self._updateProgressWindow

        title = P_("Formatting DASD Device", "Formatting DASD Devices", c)
        msg = P_("Preparing %d DASD device for use with Linux..." % c,
                 "Preparing %d DASD devices for use with Linux..." % c, c)

        if intf:
            if self.totalCylinders:
                pw = intf.progressWindow(title, msg, 1.0)
            else:
                pw = intf.progressWindow(title, msg, 100, pulse=True)

        for dasd, bypath in self._dasdlist:
            log.info("Running dasdfmt on %s" % (bypath,))
            arglist = argv + ["/dev/" + dasd]

            try:
                if intf and self.totalCylinders:
                    ret = iutil.execWithCallback(self.dasdfmt, arglist,
                                                 stdout=out, stderr=err,
                                                 callback=update,
                                                 callback_data=pw,
                                                 echo=False)
                    rc = ret.rc
                elif intf:
                    ret = iutil.execWithPulseProgress(self.dasdfmt, arglist,
                                                      stdout=out, stderr=err,
                                                      progress=pw)
                    rc = ret.rc
                else:
                    rc = iutil.execWithRedirect(self.dasdfmt, arglist,
                                                stdout=out, stderr=err)
            except Exception as e:
                raise DasdFormatError(e, bypath)

            if rc:
                raise DasdFormatError("dasdfmt failed: %s" % rc, bypath)

        if intf:
            pw.pop()

    def addDASD(self, dasd):
        """ Adds a DASDDevice to the internal list of DASDs. """
        if dasd:
            self._devices.append(dasd)

    def clear_device_list(self):
        """ Clear the device list to force re-populate on next access. """
        self._devices = []

    def write(self):
        """ Write /etc/dasd.conf to target system for all DASD devices
            configured during installation.
        """
        if self._devices == []:
            return

        f = open(os.path.realpath(ROOT_PATH + "/etc/dasd.conf"), "w")
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

# Create DASD singleton
DASD = DASD()

# vim:tw=78:ts=4:et:sw=4
