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

from pyanaconda.constants import *
from udev import *
import os
from pyanaconda import iutil
from pyanaconda.flags import flags
import logging
import shutil
import time
import hashlib
import random
import itertools
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

has_libiscsi = True
try:
    import libiscsi
except ImportError:
    has_libiscsi = False

# Note that stage2 copies all files under /sbin to /usr/sbin
ISCSID=""
INITIATOR_FILE="/etc/iscsi/initiatorname.iscsi"

ISCSI_MODULES=['cxgb3i', 'bnx2i', 'be2iscsi']

def has_iscsi():
    global ISCSID

    if not os.access("/sys/module/iscsi_tcp", os.X_OK):
        return False

    if not ISCSID:
        location = iutil.find_program_in_path("iscsid")
        if not location:
            return False
        ISCSID = location
        log.info("ISCSID is %s" % (ISCSID,))

    return True

def randomIname():
    """Generate a random initiator name the same way as iscsi-iname"""

    s = "iqn.1994-05.com.domain:01."
    m = hashlib.md5()
    u = os.uname()
    for i in u:
        m.update(i)
    dig = m.hexdigest()

    for i in range(0, 6):
        s += dig[random.randrange(0, 32)]
    return s

class iscsi(object):
    """ iSCSI utility class.

        This class will automatically discover and login to iBFT (or
        other firmware) configured iscsi devices when the startup() method
        gets called. It can also be used to manually configure iscsi devices
        through the addTarget() method.

        As this class needs to make sure certain things like starting iscsid
        and logging in to firmware discovered disks only happens once
        and as it keeps a global list of all iSCSI devices it is implemented as
        a Singleton.
    """

    def __init__(self):
        # Dictionary of discovered targets containing list of (node,
        # logged_in) tuples.
        self.discovered_targets = {}
        # This list contains nodes discovered through iBFT (or other firmware)
        self.ibftNodes = []
        self._initiator = ""
        self.initiatorSet = False
        self.started = False
        self.ifaces = {}

        if flags.ibft:
            try:
                initiatorname = libiscsi.get_firmware_initiator_name()
                self._initiator = initiatorname
                self.initiatorSet = True
            except Exception:
                pass

    # So that users can write iscsi() to get the singleton instance
    def __call__(self):
        return self

    def _getInitiator(self):
        if self._initiator != "":
            return self._initiator

        return randomIname()

    def _setInitiator(self, val):
        if self.initiatorSet and val != self._initiator:
            raise ValueError, _("Unable to change iSCSI initiator name once set")
        if len(val) == 0:
            raise ValueError, _("Must provide an iSCSI initiator name")
        self._initiator = val

    initiator = property(_getInitiator, _setInitiator)

    def active_nodes(self, target=None):
        """Nodes logged in to"""
        if target:
            return [node for (node, logged_in) in
                    self.discovered_targets.get(target, [])
                    if logged_in]
        else:
            return [node for (node, logged_in) in
                    itertools.chain(*self.discovered_targets.values())
                    if logged_in] + self.ibftNodes

    def _getMode(self):
        if not self.active_nodes():
            return "none"
        if self.ifaces:
            return "bind"
        else:
            return "default"

    mode = property(_getMode)

    def _mark_node_active(self, node, active=True):
        """Mark node as one logged in to

           Returns False if not found
        """
        for target_nodes in self.discovered_targets.values():
            for nodeinfo in target_nodes:
                if nodeinfo[0] is node:
                    nodeinfo[1] = active
                    return True
        return False


    def _startIBFT(self):
        if not flags.ibft:
            return

        try:
            found_nodes = libiscsi.discover_firmware()
        except Exception:
            log.info("iscsi: No IBFT info found.");
            # an exception here means there is no ibft firmware, just return
            return

        for node in found_nodes:
            try:
                node.login()
                log.info("iscsi IBFT: logged into %s at %s:%s through %s" % (
                    node.name, node.address, node.port, node.iface))
                self.ibftNodes.append(node)
            except IOError as e:
                log.error("Could not log into ibft iscsi target %s: %s" %
                          (node.name, str(e)))
                pass

        self.stabilize()

    def stabilize(self):
        # Wait for udev to create the devices for the just added disks

        # It is possible when we get here the events for the new devices
        # are not send yet, so sleep to make sure the events are fired
        time.sleep(2)
        udev_settle()

    def create_interfaces(self, ifaces):
        for iface in ifaces:
            iscsi_iface_name = "iface%d" % len(self.ifaces)
            #iscsiadm -m iface -I iface0 --op=new
            iutil.execWithRedirect("iscsiadm",
                                   ["-m", "iface", "-I", iscsi_iface_name, "--op=new"],
                                   stdout="/dev/tty5",
                                   stderr="/dev/tty5")
            #iscsiadm -m iface -I iface0 --op=update -n iface.net_ifacename -v eth0
            iutil.execWithRedirect("iscsiadm",
                                   ["-m", "iface", "-I", iscsi_iface_name,
                                    "--op=update", "-n",
                                    "iface.net_ifacename", "-v", iface],
                                   stdout="/dev/tty5",
                                   stderr="/dev/tty5")

            self.ifaces[iscsi_iface_name] = iface
            log.debug("created_interface %s:%s" % (iscsi_iface_name, iface))

    def delete_interfaces(self):
        if not self.ifaces:
            return None
        for iscsi_iface_name in self.ifaces:
            #iscsiadm -m iface -I iface0 --op=delete
            iutil.execWithRedirect("iscsiadm",
                                   ["-m", "iface", "-I", iscsi_iface_name,
                                    "--op=delete"],
                                   stdout="/dev/tty5",
                                   stderr="/dev/tty5")
        self.ifaces = {}

    def startup(self):
        if self.started:
            return

        if not has_iscsi():
            return

        if self._initiator == "":
            log.info("no initiator set")
            return

        log.debug("Setting up %s" % (INITIATOR_FILE, ))
        log.info("iSCSI initiator name %s", self.initiator)
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
        iutil.execWithRedirect('modprobe', ['-a'] + ISCSI_MODULES,
                               stdout="/dev/tty5", stderr="/dev/tty5")
        # iscsiuio is needed by Broadcom offload cards (bnx2i). Currently
        # not present in iscsi-initiator-utils for Fedora.
        try:
            iscsiuio = iutil.find_program_in_path('iscsiuio',
                                                   raise_on_error=True)
        except RuntimeError:
            log.info("iscsi: iscsiuio not found.")
        else:
            log.debug("iscsi: iscsiuio is at %s" % iscsiuio)
            iutil.execWithRedirect(iscsiuio, [],
                                   stdout="/dev/tty5", stderr="/dev/tty5")
        # run the daemon
        iutil.execWithRedirect(ISCSID, [],
                               stdout="/dev/tty5", stderr="/dev/tty5")
        time.sleep(1)

        self._startIBFT()
        self.started = True

    def discover(self, ipaddr, port="3260", username=None, password=None,
                  r_username=None, r_password=None, intf=None):
        """
        Discover iSCSI nodes on the target available for login.

        If we are logged in a node discovered for specified target
        do not do the discovery again as it can corrupt credentials
        stored for the node (setAuth and getAuth are using database
        in /var/lib/iscsi/nodes which is filled by discovery). Just
        return nodes obtained and stored in the first discovery
        instead.

        Returns list of nodes user can log in.
        """
        authinfo = None

        if not has_iscsi():
            raise IOError, _("iSCSI not available")
        if self._initiator == "":
            raise ValueError, _("No initiator name set")

        if self.active_nodes((ipaddr, port)):
            log.debug("iSCSI: skipping discovery of %s:%s due to active nodes" %
                      (ipaddr, port))
        else:
            if username or password or r_username or r_password:
                # Note may raise a ValueError
                authinfo = libiscsi.chapAuthInfo(username=username,
                                                 password=password,
                                                 reverse_username=r_username,
                                                 reverse_password=r_password)
            self.startup()

            # Note may raise an IOError
            found_nodes = libiscsi.discover_sendtargets(address=ipaddr,
                                                        port=int(port),
                                                        authinfo=authinfo)
            if found_nodes is None:
                return None
            self.discovered_targets[(ipaddr, port)] = []
            for node in found_nodes:
                self.discovered_targets[(ipaddr, port)].append([node, False])
                log.debug("discovered iSCSI node: %s" % node.name)

        # only return the nodes we are not logged into yet
        return [node for (node, logged_in) in
                self.discovered_targets[(ipaddr, port)]
                if not logged_in]

    def log_into_node(self, node, username=None, password=None,
                  r_username=None, r_password=None, intf=None):
        """
        Raises IOError.
        """
        rc = False # assume failure
        msg = ""

        if intf:
            w = intf.waitWindow(_("Logging in to iSCSI node"),
                                _("Logging in to iSCSI node %s") % node.name)
        try:
            authinfo = None
            if username or password or r_username or r_password:
                # may raise a ValueError
                authinfo = libiscsi.chapAuthInfo(username=username,
                                                 password=password,
                                                 reverse_username=r_username,
                                                 reverse_password=r_password)
            node.setAuth(authinfo)
            node.login()
            rc = True
            log.info("iSCSI: logged into %s at %s:%s through %s" % (
                    node.name, node.address, node.port, node.iface))
            if not self._mark_node_active(node):
                log.error("iSCSI: node not found among discovered")
        except (IOError, ValueError) as e:
            msg = str(e)
            log.warning("iSCSI: could not log into %s: %s" % (node.name, msg))
        if intf:
            w.pop()

        return (rc, msg)

    # NOTE: the same credentials are used for discovery and login
    #       (unlike in UI)
    def addTarget(self, ipaddr, port="3260", user=None, pw=None,
                  user_in=None, pw_in=None, intf=None, target=None, iface=None):
        found = 0
        logged_in = 0

        found_nodes = self.discover(ipaddr, port, user, pw, user_in, pw_in,
                                    intf)
        if found_nodes == None:
            raise IOError, _("No iSCSI nodes discovered")

        for node in found_nodes:
            if target and target != node.name:
                log.debug("iscsi: skipping logging to iscsi node '%s'" %
                          node.name)
                continue
            if iface:
                node_net_iface = self.ifaces.get(node.iface, node.iface)
                if iface != node_net_iface:
                    log.debug("iscsi: skipping logging to iscsi node '%s' via %s" %
                               (node.name, node_net_iface))
                    continue

            found = found + 1

            (rc, msg) = self.log_into_node(node, user, pw, user_in, pw_in,
                                           intf)
            if rc:
                logged_in = logged_in +1

        if found == 0:
            raise IOError, _("No new iSCSI nodes discovered")

        if logged_in == 0:
            raise IOError, _("Could not log in to any of the discovered nodes")

        self.stabilize(intf)

    def write(self, storage):
        if not self.initiatorSet:
            return

        # set iscsi nodes to autostart
        root = storage.rootDevice
        for node in self.active_nodes():
            autostart = True
            disks = self.getNodeDisks(node, storage)
            for disk in disks:
                # nodes used for root get started by the initrd
                if root.dependsOn(disk):
                    autostart = False

            if autostart:
                node.setParameter("node.startup", "automatic")

        if not os.path.isdir(ROOT_PATH + "/etc/iscsi"):
            os.makedirs(ROOT_PATH + "/etc/iscsi", 0755)
        fd = os.open(ROOT_PATH + INITIATOR_FILE, os.O_RDWR | os.O_CREAT)
        os.write(fd, "InitiatorName=%s\n" %(self.initiator))
        os.close(fd)

        # copy "db" files.  *sigh*
        if os.path.isdir(ROOT_PATH + "/var/lib/iscsi"):
            shutil.rmtree(ROOT_PATH + "/var/lib/iscsi")
        if os.path.isdir("/var/lib/iscsi"):
            shutil.copytree("/var/lib/iscsi", ROOT_PATH + "/var/lib/iscsi",
                            symlinks=True)

    def getNode(self, name, address, port, iface):
        for node in self.active_nodes():
            if node.name == name and node.address == address and \
               node.port == int(port) and node.iface == iface:
                return node

        return None

    def getNodeDisks(self, node, storage):
        nodeDisks = []
        iscsiDisks = storage.devicetree.getDevicesByType("iscsi")
        for disk in iscsiDisks:
            if disk.node == node:
                nodeDisks.append(disk)

        return nodeDisks

# Create iscsi singleton
iscsi = iscsi()

# vim:tw=78:ts=4:et:sw=4
