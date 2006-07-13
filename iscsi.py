#
# iscsi.py - iscsi class
#
# Copyright 2005, 2006 IBM, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import string
import signal
import iutil
from flags import flags
import logging
import shutil
log = logging.getLogger("anaconda")

from rhpl.translate import _, N_


# Note that stage2 copies all files under /sbin to /usr/sbin
ISCSID="/usr/sbin/iscsid"
ISCSIADM = "/usr/sbin/iscsiadm"
ISCSID_DB_DIR="/var/db/iscsi"
INITIATOR_FILE="/etc/initiatorname.iscsi"

class iscsi:
    def __init__(self):
        self.targets = []
        self.ipaddr = ""
        self.port = "3260"
        self.initiator = ""
        self.iscsidStarted = False


    def action(self, action, ipaddr = None):
        #
        # run action for all iSCSI targets.
        #
        # For each record (line of output) in:
        #     iscsiadm -m node
        #
        # Where each line in the output is of the form:
        #     [recnum] stuff
        #
        # Issue the "action" request to recnum.
        #
        argv = [ "-m", "node" ]

        if ipaddr is not None:
            argv.extend(["-p", ipaddr])

        log.info("going to run iscsiadm: %s" %(argv,))
        records = iutil.execWithCapture(ISCSIADM, argv)
        for line in records.split("\n"):
            if line and line.find("no records found!") == -1:
                recnum = line.split()[0][1:-1]
                argv = [ "-m", "node", "-r", "%s" % (recnum,),
                         "%s" % (action,) ]
                rc = iutil.execWithRedirect(ISCSIADM, argv, searchPath = 1,
                                            stdout = "/dev/tty5",
                                            stderr = "/dev/tty5")
                if rc != 0:
                    log.info("iscsiadm failed!")
                    continue

                if action != "--login":
                    continue
                
                # ... and now we have to make it start automatically
                argv = [ "-m", "node", "-r", "%s" %(recnum,),
                         "-o", "update", "-n", "node.startup",
                         "-v", "automatic" ]
                iutil.execWithRedirect(ISCSIADM, argv, searchPath = 1,
                                       stdout = "/dev/tty5",
                                       stderr = "/dev/tty5")

    def shutdown(self):
        if not self.iscsidStarted:
            return

        log.info("iSCSI shutdown")
        self.action("--logout")

        # XXX use iscsiadm shutdown when it's available.
        argv = [ "--no-headers", "-C", "%s" % (ISCSID,) ]
        psout = iutil.execWithCapture("/usr/bin/ps", argv)
        for line in psout.split("\n"):
            if line:
                pid = string.atoi(string.split(line)[0])
                log.info("Killing %s %d" % (ISCSID, pid))
                os.kill(pid, signal.SIGKILL)
        self.iscsidStarted = False;

    def discoverTarget(self, ipaddr, port, intf = None):
        if not self.iscsidStarted:
            self.startup(intf)
        if flags.test:
            return
            
        argv = [ "-m", "discovery", "-t", "st", "-p", 
                 "%s:%s" % (ipaddr, port) ]
        log.info("going to run with args: %s" %(argv,))
        iutil.execWithRedirect(ISCSIADM, argv,
                               stdout = "/dev/tty5", stderr="/dev/tty5")

    def loginTarget(self, ipaddr = None):
        if flags.test:
            return
        self.action("--login", ipaddr)

    def startup(self, intf = None):
        if flags.test:
            return
        if not self.initiator:
            log.info("no initiator set")
            return
        if self.iscsidStarted:
            return
        
        log.info("iSCSI initiator name %s", self.initiator)

        if intf:
            w = intf.waitWindow(_("Initializing iSCSI initiator"),
                                _("Initializing iSCSI initiator"))

        log.debug("Setting up %s" % (INITIATOR_FILE, ))
        if os.path.exists(INITIATOR_FILE):
            os.unlink(INITIATOR_FILE)
        fd = os.open(INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        if not os.path.exists(ISCSID_DB_DIR):
            iutil.mkdirChain(ISCSID_DB_DIR)
        iutil.execWithRedirect(ISCSID, [], searchPath = 1)
        self.iscsidStarted = True

        for t in self.targets:
            idx = t.rfind(":")
            if idx == -1:
                ipaddr = t
                port = "3260"
            else:
                ipaddr = t[:idx]
                port = t[idx:]

            self.discoverTarget(ipaddr, port, intf)
            self.loginTarget(ipaddr)

        if intf:
            w.pop()

    def writeKS(self):
        # XXX Useful if we have auto-generated kickstart files.
        return

    def write(self, instPath):
        if not self.ipaddr:
            return

        fd = os.open(instPath + INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        if not os.path.isdir(instPath  + "/var/db"):
            iutil.mkdirChain(instPath + "/var/db")
        shutil.copytree("/var/db/iscsi", instPath + "/var/db/iscsi")

# vim:tw=78:ts=4:et:sw=4
