#
# iscsi.py - iscsi class
#
# Copyright (C) 2005, 2006  IBM, Inc.  All rights reserved.
# Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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

from constants import *
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)


# Note that stage2 copies all files under /sbin to /usr/sbin
global ISCSID
ISCSID=""
global ISCSIADM
ISCSIADM = ""
INITIATOR_FILE="/etc/iscsi/initiatorname.iscsi"

def find_iscsi_files():
    global ISCSID
    if ISCSID == "":
        for dir in ("/usr/sbin", "/tmp/updates", "/mnt/source/RHupdates"):
            path="%s/iscsid" % (dir,)
            if os.access(path, os.X_OK):
                ISCSID=path
    global ISCSIADM
    if ISCSIADM == "":
        for dir in ("/usr/sbin", "/tmp/updates", "/mnt/source/RHupdates"):
            path="%s/iscsiadm" % (dir,)
            if os.access(path, os.X_OK):
                ISCSIADM=path

def has_iscsi():
    find_iscsi_files()
    if ISCSID == "" or ISCSIADM == "":
        return False

    log.info("ISCSID is %s" % (ISCSID,))
    log.info("ISCSIADM is %s" % (ISCSIADM,))

    # make sure the module is loaded
    if not os.access("/sys/module/iscsi_tcp", os.X_OK):
        return False
    return True

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
        self._nodes = []

        find_iscsi_files()

    def _getPortal(self):
        if self._portal is None:
            argv = [ "-m", "discovery", "-t", "st", "-p", self.ipaddr ]
            log.debug("iscsiadm %s" %(string.join(argv),))
            records = iutil.execWithCapture(ISCSIADM, argv)
            records = records.strip()
            for line in records.split("\n"):
                log.debug("  %s" % (line,))
                if not line or line.find("found!") != -1:
                    log.warn("no record found!")
                    continue
                pnlist = line.split()
                if len(pnlist) != 2:
                    log.warn("didn't get what we expected from iscsiadm")
                    continue
                (portal, node) = pnlist
                if portal.startswith(self.ipaddr):
                    self._portal = portal
                    self._nodes.append(node)
        return self._portal
    portal = property(_getPortal)

    def _getNode(self):
        if len(self._nodes) == 0:
            # _getPortal() fills the list, if possible.
            self._getPortal()
        return self._nodes
    nodes = property(_getNode)

    def discover(self):
        argv = [ "-m", "discovery", "-t", "st", "-p", 
                 "%s:%s" % (self.ipaddr, self.port) ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        rc = iutil.execWithRedirect(ISCSIADM, argv,
                                    stdout = "/dev/tty5", stderr="/dev/tty5")
        if rc != 0:
            log.warn("iscsiadm failed to discover on %s" %(self.ipaddr,))
            return False
        return True

    def startNode(self, node):
        if node is None or self.portal is None:
            log.warn("unable to find portal information")
            return

        argv = [ "-m", "node", "-T", node, "-p", self.portal,
                 "-o", "update", "-n", "node.conn[0].startup",
                 "-v", "automatic" ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        iutil.execWithRedirect(ISCSIADM, argv,
                               stdout = "/dev/tty5", stderr="/dev/tty5")

    def loginToNode(self, node):
        if node is None or self.portal is None:
            log.warn("unable to find portal information")
            return

        argv = [ "-m", "node", "-T", node, "-p", self.portal, "--login" ]
        log.debug("iscsiadm %s" %(string.join(argv),))
        rc = iutil.execWithRedirect(ISCSIADM, argv,
                                    stdout = "/dev/tty5", stderr="/dev/tty5")
        if rc != 0:
            log.warn("iscsiadm failed to login to %s" %(self.ipaddr,))
            return False
        return True

    def login(self):
        if len(self.nodes) == 0 or self.portal is None:
            log.warn("unable to find portal information")
            return False


        ret = False
        for node in self.nodes:
            if self.loginToNode(node):
                ret = True
                self.startNode(node)

        # we return True if there were any successful logins for our portal.
        return ret

    def logout(self):
        for node in self.nodes:
            argv = [ "-m", "node", "-T", node, "-p", self.portal, "--logout" ]
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
        self.fwinfo = self._queryFirmware()
        self.targets = []
        self._initiator = ""
        self.initiatorSet = False
        self.oldInitiatorFile = None
        self.iscsidStarted = False

        if self.fwinfo and self.fwinfo.has_key("iface.initiatorname"):
            self._initiator = self.fwinfo["iface.initiatorname"]
            self.initiatorSet = True
            self.startup()

    def _getInitiator(self):
        if self._initiator != "":
            return self._initiator

        if self.fwinfo and self.fwinfo.has_key("iface.initiatorname"):
            return self.fwinfo["iface.initiatorname"]
        else:
            return randomIname()

    def _setInitiator(self, val):
        if self._initiator != "" and val != self._initiator:
            raise ValueError, "Unable to change iSCSI initiator name once set"
        if len(val) == 0:
            raise ValueError, "Must provide a non-zero length string"
        self._initiator = val
        self.initiatorSet = True

    initiator = property(_getInitiator, _setInitiator)

    def _queryFirmware(self):
        # Example:
        # [root@elm3b87 ~]# iscsiadm -m fw
        # iface.initiatorname = iqn.2007-05.com.ibm.beaverton.elm3b87:01
        # iface.hwaddress = 00:14:5e:b3:8e:b2
        # node.name = iqn.1992-08.com.netapp:sn.84183797
        # node.conn[0].address = 9.47.67.152
        # node.conn[0].port = 3260

        find_iscsi_files()

        if not has_iscsi():
            return

        retval = {}

        argv = [ "-m", "fw" ]
        log.debug("queryFirmware: ISCSIADM is %s" % (ISCSIADM,))
        result = iutil.execWithCapture(ISCSIADM, argv)
        result = result.strip()
        for line in result.split("\n"):
            SPLIT = " = "
            idx = line.find(SPLIT)
            if idx != -1:
                lhs = line[:idx]
                rhs = line[idx+len(SPLIT):]
                retval[lhs] = rhs

        return retval

    def _startIscsiDaemon(self):
        psout = iutil.execWithCapture("/usr/bin/pidof", ["iscsid"])
        if psout.strip() == "":
            log.info("iSCSI startup")
            iutil.execWithRedirect(ISCSID, [],
                                   stdout="/dev/tty5", stderr="/dev/tty5")
            self.iscsidStarted = True
            time.sleep(2)

    def _stopIscsiDaemon(self):
        result = iutil.execWithCapture(ISCSIADM, ["-k", "0"])
        result.strip()
        if result == "":
            return

        psout = iutil.execWithCapture("/usr/bin/pidof", ["iscsid"])
        if psout.strip() != "":
            log.info("iSCSI shutdown")
            for t in self.targets:
                t.logout()

            for pidstr in psout.split():
                pid = string.atoi(pidstr)
                login.info("killing %s %d" % (ISCSID, pid))

                os.kill(pid, signal.SIGKILL)

            self.iscsidStarted = False

    def shutdown(self):
        if not has_iscsi():
            return

        if flags.test:
            if self.oldInitiatorFile != None:
                f = open(INITIATOR_FILE, "w")
                for line in self.oldInitiatorFile:
                    f.write(line)
                f.close ()
                self.oldInitiatorFile = None
        self._stopIscsiDaemon()

    def loginToDefaultDrive(self):
        # Example:
        # [root@elm3b87 ~]# iscsiadm -m fw -l
        # Logging in to [iface: default, target: iqn.1992-08.com.netapp:sn.84183797, portal: 9.47.67.152,3260]

        find_iscsi_files()

        argv = [ "-m", "fw", "-l" ]
        result = iutil.execWithCapture(ISCSIADM, argv)

        TARGET = "target: "
        PORTAL = ", portal: "
        END = "]"
        idxTarget = result.find(TARGET)
        idxPortal = result.find(PORTAL)
        idxEnd = result.find(END)

        if idxTarget == -1 or idxPortal == -1 or idxEnd == -1:
            return None

        target = result[idxTarget + len(TARGET) : idxPortal]
        portal = result[idxPortal + len(PORTAL) : idxEnd]
        port = 3260
        idxPort = portal.find(',')
        if idxPort != -1:
            port = portal[idxPort + 1 :]
            portal = portal[:idxPort]

        return (target, portal, port)

    def startup(self, intf = None):
        if not has_iscsi():
            return

        if not self.initiatorSet:
            log.info("no initiator set")
            return
        if flags.test:
            if os.access(INITIATOR_FILE, os.R_OK):
                f = open(INITIATOR_FILE, "r")
                self.oldInitiatorFile = f.readlines()
                f.close()

        if intf:
            w = intf.waitWindow(_("Initializing iSCSI initiator"),
                                _("Initializing iSCSI initiator"))

        log.debug("Setting up %s" % (INITIATOR_FILE, ))
        log.info("iSCSI initiator name %s", self.initiator)
        if os.path.exists(INITIATOR_FILE):
            os.unlink(INITIATOR_FILE)
        if not os.path.isdir("/etc/iscsi"):
            os.makedirs("/etc/iscsi", 0755)
        fd = os.open(INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        if not os.path.isdir("/var/lib/iscsi"):
            os.makedirs("/var/lib/iscsi", 0660)
        for dir in ['nodes','send_targets','ifaces']:
            fulldir = "/var/lib/iscsi/%s" % (dir,)
            if not os.path.isdir(fulldir):
                os.makedirs(fulldir, 0660)

        self._startIscsiDaemon()

        # If there is a default drive in the iSCSI configuration, then
        # automatically attach to it. Do this before testing the initiator
        # name, because it is provided by the iBFT too

        # this will actually log us in, but it won't create the iscsi db
        # entries.
        default = self.loginToDefaultDrive()
        if not default is None:
            (node, ipaddr, port) = default
            t = iscsiTarget(ipaddr, port, None, None)
            # this actually creates the entries.
            t.discover()
            # and this sets them to auto-start
            t.startNode(node)

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
        f.write("iscsiname %s\n" %(self.initiator,))
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

        if not flags.test:
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
