#
# iscsi.py - iscsi class
#
# Copyright 2005, 2006 IBM, Inc.,
# Copyright 2006  Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import iutil
import isys
from flags import flags
import logging
import shutil
import time
import md5, random
log = logging.getLogger("anaconda")

from rhpl.translate import _, N_

has_libiscsi = True
try:
    import libiscsi
except ImportError:
    has_libiscsi = False

# Note that stage2 copies all files under /sbin to /usr/sbin
ISCSID=""
INITIATOR_FILE="/etc/iscsi/initiatorname.iscsi"

def find_iscsi_files():
    global ISCSID
    if ISCSID == "":
        for dir in ("/usr/sbin", "/tmp/updates", "/mnt/source/RHupdates"):
            path="%s/iscsid" % (dir,)
            if os.access(path, os.X_OK):
                ISCSID=path

def has_iscsi():
    find_iscsi_files()
    if ISCSID == "" or not has_libiscsi:
        return False

    log.info("ISCSID is %s" % (ISCSID,))

    # make sure the module is loaded
    if not os.access("/sys/module/iscsi_tcp", os.X_OK):
        return False
    return True

def randomIname():
    """Generate a random initiator name the same way as iscsi-iname"""
    
    s = "iqn.1994-05.com.rhel:01."
    m = md5.md5()
    u = os.uname()
    for i in u:
        m.update(i)
    dig = m.hexdigest()
    
    for i in range(0, 6):
        s += dig[random.randrange(0, 32)]
    return s

def stabilize(intf = None):
    # Wait for udev to create the devices for the just added disks
    if intf:
        w = intf.waitWindow(_("Scanning iSCSI nodes"),
                            _("Scanning iSCSI nodes"))
    time.sleep(2)

    # ensure we have device nodes for our partitions
    isys.flushDriveDict()
    iutil.makeDriveDeviceNodes()

    if intf:
        w.pop()

class iscsi(object):
    def __init__(self):
        self.nodes = []
        self._initiator = ""
        self.initiatorSet = False
        self.started = False

        if flags.ibft:
            try:
                initiatorname = libiscsi.get_firmware_initiator_name()
                self._initiator = initiatorname
                self.initiatorSet = True
            except:
                pass

    def _getInitiator(self):
        if self._initiator != "":
            return self._initiator

        return randomIname()

    def _setInitiator(self, val):
        if self.initiatorSet and val != self._initiator:
            raise ValueError, "Unable to change iSCSI initiator name once set"
        if len(val) == 0:
            raise ValueError, "Must provide a non-zero length string"
        self._initiator = val

    initiator = property(_getInitiator, _setInitiator)

    def _startIBFT(self, intf = None):
        if not flags.ibft:
            return

        try:
            found_nodes = libiscsi.discover_firmware()
        except:
            # an exception here means there is no ibft firmware, just return
            return

        for node in found_nodes:
            try:
                node.login()
                self.nodes.append(node)
            except:
                # FIXME, what to do when we cannot log in to a firmware
                # provided node ??
                pass

        stabilize(intf)

    def startup(self, intf = None):
        if self.started:
            return

        if not has_iscsi():
            return

        if self._initiator == "":
            log.info("no initiator set")
            return

        if intf:
            w = intf.waitWindow(_("Initializing iSCSI initiator"),
                                _("Initializing iSCSI initiator"))

        log.debug("Setting up %s" % (INITIATOR_FILE, ))
        log.info("iSCSI initiator name %s" % (self.initiator,))
        if os.path.exists(INITIATOR_FILE):
            os.unlink(INITIATOR_FILE)
        if not os.path.isdir("/etc/iscsi"):
            os.makedirs("/etc/iscsi", 0755)
        fd = os.open(INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)
        self.initiatorSet = True

        for dir in ['ifaces','isns','nodes','send_targets','slp','static']:
            fulldir = "/var/lib/iscsi/%s" % (dir,)
            if not os.path.isdir(fulldir):
                os.makedirs(fulldir, 0755)

        log.info("iSCSI startup")
        iutil.execWithRedirect(ISCSID, [],
                               stdout="/dev/tty5", stderr="/dev/tty5")
        time.sleep(1)

        if intf:
            w.pop()

        self._startIBFT(intf)
        self.started = True

    def addTarget(self, ipaddr, port="3260", user=None, pw=None,
                  user_in=None, pw_in=None, intf=None):
        authinfo = None
        found = 0
        logged_in = 0

        if not has_iscsi():
            raise IOError, _("iSCSI not available")
        if self._initiator == "":
            raise ValueError, _("No initiator name set")

        if user or pw or user_in or pw_in:
            # Note may raise a ValueError
            authinfo = libiscsi.chapAuthInfo(username=user, password=pw,
                                             reverse_username=user_in,
                                             reverse_password=pw_in)
        self.startup(intf)

        # Note may raise an IOError
        found_nodes = libiscsi.discover_sendtargets(address=ipaddr,
                                                    port=int(port),
                                                    authinfo=authinfo)
        if found_nodes == None:
            raise IOError, _("No iSCSI nodes discovered")

        if intf:
            w = intf.waitWindow(_("Logging in to iSCSI nodes"),
                                _("Logging in to iSCSI nodes"))

        for node in found_nodes:
            # skip nodes we already have
            if node in self.nodes:
                continue

            found = found + 1
            try:
                if (authinfo):
                    node.setAuth(authinfo)
                node.login()
                self.nodes.append(node)
                logged_in = logged_in + 1
            except:
                # some nodes may require different credentials
                pass

        if intf:
            w.pop()

        if found == 0:
            raise IOError, _("No new iSCSI nodes discovered")

        if logged_in == 0:
            raise IOError, _("Could not log in to any of the discovered nodes")

        stabilize(intf)

    def writeKS(self, f):
        if not self.initiatorSet:
            return
        f.write("iscsiname %s\n" %(self.initiator,))
        for n in self.nodes:
            f.write("iscsi --ipaddr %s --port %s" %(n.address, n.port))
            auth = n.getAuth()
            if auth:
                f.write(" --user %s" % auth.username)
                f.write(" --password %s" % auth.password)
                if len(auth.reverse_username):
                    f.write(" --reverse-user %s" % auth.reverse_username)
                if len(auth.reverse_password):
                    f.write(" --reverse-password %s" % auth.reverse_password)
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
            if os.path.isdir(instPath + "/var/lib/iscsi"):
                shutil.rmtree(instPath + "/var/lib/iscsi")
            if os.path.isdir("/var/lib/iscsi"):
                shutil.copytree("/var/lib/iscsi", instPath + "/var/lib/iscsi",
                                symlinks=True)

# vim:tw=78:ts=4:et:sw=4
