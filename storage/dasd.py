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

import iutil
import isys
import sys
import os
from storage.errors import DasdFormatError
from storage.devices import deviceNameToDiskByPath
from constants import *
from flags import flags
from baseudev import udev_trigger

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

class DASD:
    """ Controlling class for DASD interaction before the storage code in
        anaconda has initialized.

        The DASD class can determine if any DASD devices on the system are
        unformatted and can perform a dasdfmt on them.
    """

    def __init__(self):
        self._dasdlist = []
        self._ldldasdlist = []
        self._devices = []                  # list of DASDDevice objects
        self.totalCylinders = 0
        self._completedCylinders = 0.0
        self._maxFormatJobs = 0
        self.dasdfmt = "/sbin/dasdfmt"
        self.commonArgv = ["-y", "-d", "cdl", "-b", "4096"]
        self.started = False

    def __call__(self):
        return self

    def startup(self, intf, exclusiveDisks, zeroMbr, cdl):
        """ Look for any unformatted DASDs in the system and offer the user
            the option for format them with dasdfmt or exit the installer.

            Also check if any DASDs are LDL formatted and show a warning to
            users, since these disks will not be usable during installation.
        """
        if self.started:
            return

        self.started = True

        if not iutil.isS390():
            return

        # Trigger udev data about the dasd devices on the system
        udev_trigger(action="change", name="dasd*")

        log.info("Checking for unformatted and LDL DASD devices:")

        for device in os.listdir("/sys/block"):
            if not device.startswith("dasd"):
                continue

            statusfile = "/sys/block/%s/device/status" % (device,)
            if not os.path.isfile(statusfile):
                continue

            f = open(statusfile, "r")
            status = f.read().strip()
            f.close()

            bypath = deviceNameToDiskByPath(device)
            if not bypath:
                bypath = "/dev/" + device

            if status in ["unformatted"] and device not in exclusiveDisks:
                log.info("    %s (%s) status is %s, needs dasdfmt" % (device,
                                                                      bypath,
                                                                      status,))
                self._dasdlist.append((device, bypath))

            elif isys.isLdlDasd(device):
                log.info("     %s (%s) is an LDL DASD, needs dasdfmt" % (device,
                                                                         bypath))
                self._ldldasdlist.append((device, bypath))

        if not intf and (not zeroMbr or not cdl):
            log.info("    non-interactive kickstart install without zerombr "
                     "or clearpart --cdl "
                     "command, unable to run dasdfmt, exiting installer")
            sys.exit(0)

        # now onto formatting our DASDs
        if not len(self._dasdlist):
            log.info("    no unformatted DASD devices found")
        else:
            self.format_dasds(intf, not zeroMbr, self._dasdlist)

        if not len(self._ldldasdlist):
            log.info("    no LDL DASD devices found")
        else:
            self.format_dasds(intf, not cdl, self._ldldasdlist)

    def format_dasds(self, intf, askUser, dasdlist):
        """ Iterate through a given list of DASDs and run dasdfmt on them. """
        out = "/dev/tty5"
        err = "/dev/tty5"

        c = len(dasdlist)

        if intf and askUser:
            devs = ''
            for dasd, bypath in dasdlist:
                devs += "%s\n" % (bypath,)

            rc = intf.questionInitializeDASD(c, devs)
            if rc == 1:
                log.info("    not running dasdfmt, continuing installation")
                return

        # gather total cylinder count
        argv = ["-t", "-v"] + self.commonArgv
        for dasd, bypath in dasdlist:
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

        for dasd, bypath in dasdlist:
            log.info("Running dasdfmt on %s" % (bypath,))
            arglist = argv + ["/dev/" + dasd]

            try:
                if intf and self.totalCylinders:
                    rc = iutil.execWithCallback(self.dasdfmt, arglist,
                                                stdout=out, stderr=err,
                                                callback=update,
                                                callback_data=pw,
                                                echo=False)
                elif intf:
                    rc = iutil.execWithPulseProgress(self.dasdfmt, arglist,
                                                     stdout=out, stderr=err,
                                                     progress=pw)
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
            # each newline we see in this output means 10 more cylinders done
            self._completedCylinders += 10.0
            callback_data.set(self._completedCylinders / self.totalCylinders)

# Create DASD singleton
DASD = DASD()

# vim:tw=78:ts=4:et:sw=4
