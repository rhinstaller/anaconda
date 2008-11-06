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
import errno
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
global ISCSID
ISCSID=""
global ISCSIADM
ISCSIADM = ""
INITIATOR_FILE="/etc/iscsi/initiatorname.iscsi"
ISCSID_CONF="/etc/iscsi/iscsid.conf"

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
    def __init__(self, ipaddr, port=None, user=None, pw=None,
            user_in=None, pw_in=None):
        # FIXME: validate ipaddr
        self.ipaddr = ipaddr
        if not port: # FIXME: hack hack hack
            port = 3260
        self.port = str(port)
        self.user = user
        self.password = pw
        self.user_in = user_in
        self.password_in = pw_in
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

    def addNode(self, node):
        if node is None or self.portal is None:
            log.warn("unable to find portal information")
            return

        argv = [ "-m", "node", "-T", node, "-p", self.portal,
                 "-o", "new" ]
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
                self.addNode(node)

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

        # iface.bootproto = DHCP
        # or
        # iface.bootproto = STATIC
        # iface.ipaddress = 192.168.32.72
        # iface.subnet_mask = 255.255.252.0
        # iface.gateway = 192.168.35.254

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

        if len(result) == 0 \
                or result[0].find("iscsiadm -") != -1 \
                or result[0].find("iscsiadm: ") != -1:
            log.debug("queryFirmware: iscsiadm %s returns bad output: %s" %
                (argv,result))

            # Try querying the node records instead
            argv = [ "-m", "node", "-o", "show", "-S" ]
            result = iutil.execWithCapture(ISCSIADM, argv)

            if len(result) == 0 \
                    or result[0].find("iscsiadm -") != -1 \
                    or result[0].find("iscsiadm: ") != -1:
                log.debug("queryFirmware: iscsiadm %s returns bad output: %s" %
                    (argv,result))
                return retval

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
                log.info("killing %s %d" % (ISCSID, pid))

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
        # [root@elm3b87 ~]# iscsiadm -m discovery -t fw -l
        # Logging in to [iface: default, target: iqn.1992-08.com.netapp:sn.84183797, portal: 9.47.67.152,3260]

        find_iscsi_files()

        argv = [ "-m", "discovery", "-t", "fw", "-l" ]
        result = iutil.execWithCapture(ISCSIADM, argv)
        log.debug("iscsiadm result: %s" % (result,))

        start = result.find('[')
        end = result.rfind(']')

        if start == -1 or end == -1:
            log.warn("could not find markers.  iscsiadm returned: %s" %
                (result,))
            return

        values = {}
        for kv in string.split(result[start+1:end], ', '):
            (k, v) = string.split(kv, ': ')
            values[k] = v
        del start, end

        if not values.has_key('target'):
            log.warn("iBFT data missing target.  iscsiadm returned: %s" %
                (result,))

        if not values.has_key('portal'):
            log.warn("iBFT data missing portal.  iscsiadm returned: %s" %
                (result,))
        else:
            portal = values['portal']
            comma = portal.find(',')
            if comma == -1:
                values['port'] = 3260
            else:
                values['port'] = portal[comma+1:]
                values['portal'] = portal[0:comma]

        if not values.has_key('chap-username') or not \
                values.has_key('chap-password'):
            if values.has_key('chap-username'):
                log.warn("Invalid iBFT CHAP password.  iscsiadm returned: %s" %
                    (result,))
                return
            if values.has_key('chap-password'):
                log.warn("Invalid iBFT CHAP username.  iscsiadm returned: %s" %
                    (result,))
                return
                
        if not values.has_key('rev-chap-username') or not \
                values.has_key('rev-chap-password'):
            if values.has_key('rev-chap-username'):
                log.warn("Invalid iBFT Reverse CHAP password.  " \
                         "iscsiadm returned %s" % (result,))
                return
            if values.has_key('rev-chap-password'):
                log.warn("Invalid iBFT Reverse CHAP username.  " \
                         "iscsiadm returned %s" % (result,))
                return

        target = values['target']

        renames = {
            'portal': 'ipaddr',
            'chap-username': 'user',
            'chap-password': 'pw',
            'rev-chap-username': 'user_in',
            'rev-chap-password': 'pw_in',
            }

        for k,v in renames.items():
            if values.has_key(k):
                values[v] = values[k]
                del values[k]

        badKeys = filter(lambda x: not x in \
                          ('ipaddr','port','user','pw','user_in','pw_in'),
                         values.keys())
        for k in badKeys:
            del values[k]

        # make a new target
        self.addTarget(**values)


    def startIBFT(self):
        # If there is a default drive in the iSCSI configuration, then
        # automatically attach to it. Do this before testing the initiator
        # name, because it is provided by the iBFT too

        if flags.ibft:
            self.loginToDefaultDrive()

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
        log.info("iSCSI initiator name %s" % (self.initiator,))
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
        self.startIBFT()

        for t in self.targets:
            if not t.discover():
                continue
            t.login()

        if intf:
            w.pop()

    def addTarget(self, ipaddr, port="3260", user=None, pw=None,
                  user_in=None, pw_in=None, intf=None):
        if not self.iscsidStarted:
            self.startup(intf)
            if not self.iscsidStarted:
                # can't start for some reason.... just fallback I guess
                return

        commentUser = '#'
        commentUser_in = '#'

        if user is not None or pw is not None:
            commentUser = ''
            if user is None:
                raise ValueError, "user is required"
            if pw is None:
                raise ValueError, "pw is required"

        if user_in is not None or pw_in is not None:
            commentUser_in = ''
            if user_in is None:
                raise ValueError, "user_in is required"
            if pw_in is None:
                raise ValueError, "pw_in is required"

        # If either a user/pw pair was specified or a user_in/pw_in was
        # specified, then CHAP is specified.
        if commentUser == '' or commentUser_in == '':
            commentChap = ''
        else:
            commentChap = '#'


        oldIscsidFile = []
        try:
            f = open(ISCSID_CONF, "r")
            oldIscsidFile = f.readlines()
            f.close()
        except IOError, x:
            if x.errno != errno.ENOENT:
                raise RuntimeError, "Cannot open %s for read." % (ISCSID_CONF,)

        try:
            f = open(ISCSID_CONF, "w")
        except:
            raise RuntimeError, "Cannot open %s for write." % (ISCSID_CONF,)

        vals = {
            "node.session.auth.authmethod = ": [commentChap, "CHAP"],
            "node.session.auth.username = ": [commentUser, user],
            "node.session.auth.password = ": [commentUser, pw],
            "node.session.auth.username_in = ": [commentUser_in, user_in],
            "node.session.auth.password_in = ": [commentUser_in, pw_in],
            "discovery.sendtargets.auth.authmethod = ": [commentChap, "CHAP"],
            "discovery.sendtargets.auth.username = ": [commentUser, user],
            "discovery.sendtargets.auth.password = ": [commentUser, pw],
            "discovery.sendtargets.auth.username_in = ":
                [commentUser_in, user_in],
            "discovery.sendtargets.auth.password_in = ":
                [commentUser_in, pw_in],
            }

        for line in oldIscsidFile:
            s  = line.strip()
            # grab the cr/lf/cr+lf
            nl = line[line.find(s)+len(s):]
            found = False
            for (k, (c, v)) in vals.items():
                if line.find(k) != -1:
                    f.write("%s%s%s%s" % (c, k, v, nl))
                    found=True
                    del vals[k]
                    break
            if not found:
                f.write(line)

        for (k, (c, v)) in vals.items():
            f.write("%s%s%s\n" % (c, k, v))
        f.close ()

        t = iscsiTarget(ipaddr, port, user, pw, user_in, pw_in)
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
            if t.user_in:
                f.write(" --reverse-user %s" % (t.user_in,))
            if t.password_in:
                f.write(" --reverse-password %s" % (t.password_in,))
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
