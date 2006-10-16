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
import time
import md5, random
log = logging.getLogger("anaconda")

from rhpl.translate import _, N_

# Note that stage2 copies all files under /sbin to /usr/sbin
ISCSID="/usr/sbin/iscsid"
ISCSIADM = "/usr/sbin/iscsiadm"
INITIATOR_FILE="/etc/iscsi/initiatorname.iscsi"

class iscsiTarget:
    def __init__(self, ipaddr, port = None, user = None, pw = None):
        # FIXME: validate ipaddr
        self.ipaddr = ipaddr
        if not port: # FIXME: hack hack hack
            port = 3260
        self.port = str(port)
        self.user = user
        self.password = pw
        self._portal = None
        self._node = None

    def _getPortal(self):
        if self._portal is None:
            argv = [ "-m", "node", "-p", self.ipaddr ]
            records = iutil.execWithCapture(ISCSIADM, argv)
            for line in records.split("\n"):
                if not line or line.find("found!") != -1:
                    log.warn("no record found!")
                    return None
                if len(line.split()) != 2:
                    log.warn("didn't get what we expected from iscsiadm")
                    return None
                (self._portal, self._node) = line.split()
                if not self._portal.startswith(self.ipaddr):
                    self._portal = self._node = None
                    continue
                break
        return self._portal
    def _getNode(self):
        # FIXME: this is kind of gross....
        if self._node is None:
            p = self.portal
        return self._node
    portal = property(_getPortal)
    node = property(_getNode)

    def discover(self):
        if flags.test:
            return True

        argv = [ "-m", "discovery", "-t", "st", "-p", 
                 "%s:%s" % (self.ipaddr, self.port) ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        rc = iutil.execWithRedirect(ISCSIADM, argv,
                                    stdout = "/dev/tty5", stderr="/dev/tty5")
        if rc != 0:
            log.warn("iscsiadm failed to discover on %s" %(self.ipaddr,))
            return False
        return True

    def login(self):
        if self.node is None or self.portal is None:
            log.warn("unable to find portal information")
            return False
        argv = [ "-m", "node", "-T", self.node, "-p", self.portal, "--login" ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        rc = iutil.execWithRedirect(ISCSIADM, argv,
                                    stdout = "/dev/tty5", stderr="/dev/tty5")
        if rc != 0:
            log.warn("iscsiadm failed to login to %s" %(self.ipaddr,))
            return False

        self._autostart()
        return True

    def _autostart(self):
        argv = [ "-m", "node", "-T", self.node, "-p", self.portal,
                 "-o", "update", "-n", "node.conn[0].startup",
                 "-v", "automatic" ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        iutil.execWithRedirect(ISCSIADM, argv,
                               stdout = "/dev/tty5", stderr="/dev/tty5")

    def logout(self):
        argv = [ "-m", "node", "-T", self.node, "-p", self.portal, "--logout" ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        rc = iutil.execWithRedirect(ISCSIADM, argv,
                                    stdout = "/dev/tty5", stderr="/dev/tty5")

def randomIname():
    """Generate a random initiator name the same way as iscsi-iname"""
    
    s = "iqn.2005-03.com.max:01."
    m = md5.md5()
    u = os.uname()
    for i in u:
        m.update(i)
    dig = m.hexdigest()
    
    for i in range(0, 6):
        s += dig[random.randrange(0, 32)]
    return s

class iscsi(object):
    def __init__(self):
        self.targets = []
        self._initiator = ""
        self.initiatorSet = False
        self.iscsidStarted = False

    def _getInitiator(self):
        if self._initiator != "":
            return self._initiator
        return randomIname()
    def _setInitiator(self, val):
        if self._initiator != "" and val != self._initiator:
            raise ValueError, "Unable to change iSCSI initiator name once set"
        if len(val) == 0:
            raise ValueError, "Must provide a non-zero length string"
        self._initiator = val
        self.initiatorSet = True        
    initiator = property(_getInitiator, _setInitiator)

    def shutdown(self):
        if not self.iscsidStarted:
            return

        log.info("iSCSI shutdown")
        for t in self.targets:
            t.logout()

        # XXX use iscsiadm shutdown when it's available.
        argv = [ "--no-headers", "-C", "%s" % (ISCSID,) ]
        psout = iutil.execWithCapture("/usr/bin/ps", argv)
        for line in psout.split("\n"):
            if line:
                pid = string.atoi(string.split(line)[0])
                log.info("Killing %s %d" % (ISCSID, pid))
                os.kill(pid, signal.SIGKILL)
        self.iscsidStarted = False;

    def startup(self, intf = None):
        if flags.test:
            return
        if not self.initiatorSet:
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
        if not os.path.isdir("/etc/iscsi"):
            os.makedirs("/etc/iscsi", 0755)
        fd = os.open(INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        log.info("ISCSID is %s", ISCSID)
        iutil.execWithRedirect(ISCSID, [],
                               stdout="/dev/tty5", stderr="/dev/tty5")
        self.iscsidStarted = True
        time.sleep(2)

        for t in self.targets:
            if not t.discover():
                continue
            t.login()

        if intf:
            w.pop()

    def addTarget(self, ipaddr, port = "3260", user = None, pw = None,
                  intf = None):
        if not self.iscsidStarted:
            self.startup(intf)
            if not self.iscsidStarted:
                # can't start for some reason.... just fallback I guess
                return

        t = iscsiTarget(ipaddr, port, user, pw)
        if not t.discover():
            return
        if not t.login():
            return
        self.targets.append(t)
        return

    def writeKS(self, f):
        if not self.initiatorSet:
            return
        f.write("iscsiname %s\n", self.initiator)
        for t in self.targets:
            f.write("iscsi --ipaddr %s --port %s" %(t.ipaddr, t.port))
            if t.user:
                f.write(" --user %s" %(t.user,))
            if t.password:
                f.write(" --password %s" %(t.password,))
            f.write("\n")

    def write(self, instPath):
        if not self.initiatorSet:
            return

        if not os.path.isdir(instPath + "/etc/iscsi"):
            os.makedirs(instPath + "/etc/iscsi", 0755)
        fd = os.open(instPath + INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        # copy "db" files.  *sigh*
        if not os.path.isdir(instPath + "/var/lib/iscsi"):
            os.makedirs(instPath + "/var/lib/iscsi", 0755)
        for d in ("/var/lib/iscsi/nodes", "/var/lib/iscsi/send_targets"):
            if os.path.isdir(d):
                shutil.copytree(d, instPath + d)

# vim:tw=78:ts=4:et:sw=4
