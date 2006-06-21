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
ISCSID="iscsid"
ISCSIADM = "iscsiadm"
ISCSID_DB_DIR="/var/db/iscsi"
INITIATOR_FILE="/etc/initiatorname.iscsi"

class iscsi:
    def __init__(self):
        self.ipaddr = ""
        self.port = "3260"
        self.initiator = ""
        self.iscsidStarted = False


    def action(self, action):
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
        argv = [ ISCSIADM, "-m", "node" ]
        records = iutil.execWithCapture(argv[0], argv, searchPath = 1)
        for line in records.split("\n"):
            if line:
                recnum = line.split()[0][1:-1]
                argv = [ ISCSIADM, "-m", "node", "-r", "%s" % (recnum,),
                         "%s" % (action,) ]
                iutil.execWithRedirect(argv[0], argv, searchPath = 1,
                                       stdout = "/dev/tty5",
                                       stderr = "/dev/tty5")

                # ... and now we have to make it start automatically
                argv = [ ISCSIADM, "-m", "node", "-r", "%s" %(recnum,),
                         "-o", "update", "-n", "node.startup",
                         "-v", "automatic" ]
                iutil.execWithRedirect(argv[0], argv, searchPath = 1,
                                       stdout = "/dev/tty5",
                                       stderr = "/dev/tty5")

    def shutdown(self):
        if not self.iscsidStarted:
            return

        log.info("iSCSI shutdown")
        self.action("--logout")

        # XXX use iscsiadm shutdown when it's available.
        argv = [ "ps", "--no-headers", "-C", "%s" % (ISCSID,) ]
        psout = iutil.execWithCapture(argv[0], argv, searchPath = 1)
        for line in psout.split("\n"):
            if line:
                pid = string.atoi(string.split(line)[0])
                log.info("Killing %s %d" % (ISCSID, pid))
                os.kill(pid, signal.SIGKILL)
        self.iscsidStarted = False;


    def startup(self, intf = None):
        log.info("iSCSI IP address %s, port %s" % (self.ipaddr, self.port))
        log.info("iSCSI initiator name %s", self.initiator)

        if flags.test:
            return

        self.shutdown()

        if not self.ipaddr:
            log.info("iSCSI: Not starting, no iscsi IP address specified")
            return

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

        argv = [ ISCSID ]
        iutil.execWithRedirect(argv[0], argv, searchPath = 1)

        argv = [ ISCSIADM, "-m", "discovery", "-t", "st", "-p", 
                 "%s:%s" % (self.ipaddr, self.port) ]
        iutil.execWithRedirect(argv[0], argv, searchPath = 1,
                               stdout = "/dev/tty5", stderr="/dev/tty5")

        self.action("--login")
        self.iscsidStarted = True

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
