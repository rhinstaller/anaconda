#
# fcoe.py - fcoe class
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

import os
import iutil
import isys
import logging
import time
from flags import flags
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

_fcoe_module_loaded = False

def has_fcoe():
    global _fcoe_module_loaded
    if not _fcoe_module_loaded:
        iutil.execWithRedirect("modprobe", [ "fcoe" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
        _fcoe_module_loaded = True
        if "bnx2x" in iutil.lsmod():
            log.info("fcoe: loading bnx2fc")
            iutil.execWithRedirect("modprobe", [ "bnx2fc" ],
                                   stdout = "/dev/tty5", stderr="/dev/tty5")

    return os.access("/sys/module/fcoe", os.X_OK)

class fcoe(object):
    """ FCoE utility class.

        This class will automatically discover and connect to EDD configured
        FCoE SAN's when the startup() method gets called. It can also be
        used to manually configure FCoE SAN's through the addSan() method.

        As this class needs to make sure certain things like starting fcoe
        daemons and connecting to firmware discovered SAN's only happens once
        and as it keeps a global list of all FCoE devices it is
        implemented as a Singleton.
    """

    def __init__(self):
        self.started = False
        self.lldpadStarted = False
        self.nics = []
        self.ksnics = []

    # So that users can write fcoe() to get the singleton instance
    def __call__(self):
        return self

    def _stabilize(self, intf = None):
        if intf:
            w = intf.waitWindow(_("Connecting to FCoE SAN"),
                                _("Connecting to FCoE SAN"))

        # I have no clue how long we need to wait, this ought to do the trick
        time.sleep(10)
        iutil.execWithRedirect("udevadm", [ "settle" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
        if intf:
            w.pop()

    def _startEDD(self, intf = None):
        rc = iutil.execWithCapture("/usr/libexec/fcoe/fcoe_edd.sh", [ "-i" ],
                                   stderr="/dev/tty5")
        if not rc.startswith("NIC="):
            log.info("No FCoE EDD info found: %s" % rc)
            return

        (key, val) = rc.split("=", 1)
        if val not in isys.getDeviceProperties():
            log.error("Unknown FCoE NIC found in EDD: %s, ignoring" % val)
            return

        log.info("FCoE NIC found in EDD: %s" % val)
        self.addSan(val, dcb=True, auto_vlan=True, intf=intf)

    def startup(self, intf = None):
        if self.started:
            return

        if not has_fcoe():
            return

        self._startEDD(intf)
        self.started = True

    def _startLldpad(self):
        if self.lldpadStarted:
            return

        iutil.execWithRedirect("lldpad", [ "-d" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
        self.lldpadStarted = True

    def addSan(self, nic, dcb=False, auto_vlan=True, intf=None):
        if not has_fcoe():
            raise IOError, _("FCoE not available")

        log.info("Activating FCoE SAN attached to %s, dcb: %s autovlan: %s" %
                 (nic, dcb, auto_vlan))

        iutil.execWithRedirect("ip", [ "link", "set", nic, "up" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")

        if dcb:
            self._startLldpad()
            iutil.execWithRedirect("dcbtool", [ "sc", nic, "dcb", "on" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
            iutil.execWithRedirect("dcbtool", [ "sc", nic, "app:fcoe",
                               "e:1", "a:1", "w:1" ],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
            iutil.execWithRedirect("fipvlan", [ "-c", "-s", "-f",
                                               "-fcoe", nic],
                               stdout = "/dev/tty5", stderr="/dev/tty5")
        else:
            if auto_vlan:
                # certain network configrations require the VLAN layer module:
                iutil.execWithRedirect("modprobe", ["8021q"],
                                       stdout = "/dev/tty5", stderr="/dev/tty5")
                iutil.execWithRedirect("fipvlan", ['-c', '-s', '-f',
                                                   "-fcoe",  nic],
                                    stdout = "/dev/tty5", stderr="/dev/tty5")
            else:
                f = open("/sys/module/libfcoe/parameters/create", "w")
                f.write(nic)
                f.close()

        self._stabilize(intf)
        self.nics.append((nic, dcb, auto_vlan))

    def writeKS(self, f):
        for nic, dcb, auto_vlan in self.nics:
            if nic in self.ksnics:
                line = "fcoe --nic %s" % nic
                if dcb:
                    line += " --dcb"
                if auto_vlan:
                    line += " --autovlan"
                line += "\n"
                f.write(line)

    def write(self, instPath, anaconda):
        if not self.nics:
            return

        if not os.path.isdir(instPath + "/etc/fcoe"):
            os.makedirs(instPath + "/etc/fcoe", 0755)

        for nic, dcb, auto_vlan in self.nics:
            fd = os.open(instPath + "/etc/fcoe/cfg-" + nic,
                         os.O_RDWR | os.O_CREAT)
            os.write(fd, '# Created by anaconda\n')
            os.write(fd, '# Enable/Disable FCoE service at the Ethernet port\n')
            os.write(fd, 'FCOE_ENABLE="yes"\n')
            os.write(fd, '# Indicate if DCB service is required at the Ethernet port\n')
            if dcb:
                os.write(fd, 'DCB_REQUIRED="yes"\n')
            else:
                os.write(fd, 'DCB_REQUIRED="no"\n')
            os.write(fd, '# Indicate if VLAN discovery should be handled by fcoemon\n')
            if auto_vlan:
                os.write(fd, 'AUTO_VLAN="yes"\n')
            else:
                os.write(fd, 'AUTO_VLAN="no"\n')
            os.close(fd)

        return

# Create FCoE singleton
fcoe = fcoe()

# vim:tw=78:ts=4:et:sw=4
