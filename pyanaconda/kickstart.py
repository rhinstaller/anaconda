#
# kickstart.py: kickstart install support
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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

from storage.deviceaction import *
from storage.devices import LUKSDevice
from storage.devicelibs.lvm import getPossiblePhysicalExtents
from storage.formats import getFormat
from storage.partitioning import clearPartitions
from storage.partitioning import shouldClear
import storage.iscsi
import storage.fcoe
import storage.zfcp

from errors import *
import iutil
import isys
import os
import os.path
import tempfile
from flags import flags
from constants import *
import sys
import string
import urlgrabber
import warnings
import network
import upgrade
import pykickstart.commands as commands
from storage.devices import *
from scdate.core import zonetab
from pykickstart.base import KickstartCommand, BaseData
from pykickstart.constants import *
from pykickstart.errors import *
from pykickstart.parser import *
from pykickstart.version import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")
stderrLog = logging.getLogger("anaconda.stderr")
stdoutLog = logging.getLogger("anaconda.stdout")
from anaconda_log import logger, logLevelMap, setHandlersLevel,\
    DEFAULT_TTY_LEVEL

class AnacondaKSScript(Script):
    def run(self, chroot, serial, intf = None):
        if self.inChroot:
            scriptRoot = chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script)
        os.close(fd)
        os.chmod(path, 0700)

        # Always log stdout/stderr from scripts.  Using --logfile just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect, and to anaconda.log if the script fails.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            messages = "%s.log" % path

        if intf:
            intf.suspend()
        rc = iutil.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                    stdin = messages, stdout = messages, stderr = messages,
                                    root = scriptRoot)
        if intf:
            intf.resume()

        # Always log an error.  Only fail if we have a handle on the
        # windowing system and the kickstart file included --erroronfail.
        if rc != 0:
            log.error("Error code %s running the kickstart script at line %s" % (rc, self.lineno))

            try:
                f = open(messages, "r")
                err = f.readlines()
                f.close()
                for l in err:
                    log.error("\t%s" % l)
            except:
                err = None

            if self.errorOnFail:
                if intf != None:
                    msg = _("There was an error running the kickstart "
                            "script at line %(lineno)s.  You may examine the "
                            "output in %(msgs)s.  This is a fatal error and "
                            "installation will be aborted.  Press the "
                            "OK button to exit the installer.") \
                          % {'lineno': self.lineno, 'msgs': messages}

                    if err:
                        intf.detailedMessageWindow(_("Scriptlet Failure"), msg, err)
                    else:
                        intf.messageWindow(_("Scriptlet Failure"), msg)

                sys.exit(0)

        if serial or self.logfile is not None:
            os.chmod("%s" % messages, 0600)

class AnacondaKSPackages(Packages):
    def __init__(self):
        Packages.__init__(self)

        # Has the %packages section been seen at all?
        self.seen = False


def getEscrowCertificate(anaconda, url):
    if not url:
        return None

    if url in anaconda.storage.escrowCertificates:
        return anaconda.storage.escrowCertificates[url]

    needs_net = not url.startswith("/") and not url.startswith("file:")
    if needs_net and not network.hasActiveNetDev():
        msg = _("Escrow certificate with url %s requires network to be enabled "
                "in loader or configured in kickstart file." % url)
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(msg)
            sys.exit(1)
        else:
            stderrLog.critical(msg)
            sys.exit(1)

    log.info("escrow: downloading %s" % (url,))

    try:
        f = urlgrabber.urlopen(url)
    except urlgrabber.grabber.URLGrabError as e:
        msg = _("The following error was encountered while downloading the escrow certificate:\n\n%s" % e)
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(msg)
            sys.exit(1)
        else:
            stderrLog.critical(msg)
            sys.exit(1)

    try:
        anaconda.storage.escrowCertificates[url] = f.read()
    finally:
        f.close()

    return anaconda.storage.escrowCertificates[url]

def deviceMatches(spec):
    if not spec.startswith("/dev/"):
        spec = os.path.normpath("/dev/" + spec)

    matches = udev_resolve_glob(spec)
    dev = udev_resolve_devspec(spec)

    # udev_resolve_devspec returns None if there's no match, but we don't
    # want that ending up in the list.
    if dev and dev not in matches:
        matches.append(dev)

    return matches

# Remove any existing formatting on a device, but do not remove the partition
# itself.  This sets up an existing device to be used in a --onpart option.
def removeExistingFormat(device, storage):
    deps = storage.deviceDeps(device)
    while deps:
        leaves = [d for d in deps if d.isleaf]
        for leaf in leaves:
            storage.destroyDevice(leaf)
            deps.remove(leaf)

    storage.devicetree.registerAction(ActionDestroyFormat(device))

###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###

class Authconfig(commands.authconfig.FC3_Authconfig):
    def execute(self):
        self.anaconda.security.auth = self.authconfig

class AutoPart(commands.autopart.F12_AutoPart):
    def execute(self):
        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        self.anaconda.instClass.setDefaultPartitioning(self.anaconda.storage, self.anaconda.platform)
        self.anaconda.storage.doAutoPart = True

        if self.encrypted:
            self.anaconda.storage.encryptedAutoPart = True
            self.anaconda.storage.encryptionPassphrase = self.passphrase
            self.anaconda.storage.autoPartEscrowCert = \
                getEscrowCertificate(self.anaconda, self.escrowcert)
            self.anaconda.storage.autoPartAddBackupPassphrase = \
                self.backuppassphrase

        self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class AutoStep(commands.autostep.FC3_AutoStep):
    def execute(self):
        flags.autostep = 1
        flags.autoscreenshot = self.autoscreenshot

class Bootloader(commands.bootloader.F15_Bootloader):
    def execute(self):
        if self.location == "none":
            location = None
        elif self.location == "partition":
            location = "boot"
        else:
            location = self.location

        if self.upgrade and not self.anaconda.upgrade:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Selected upgrade mode for bootloader but not doing an upgrade")

        if self.upgrade:
            self.anaconda.bootloader.kickstart = 1
            self.anaconda.bootloader.doUpgradeOnly = 1

        if location is None:
            self.anaconda.ksdata.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            self.anaconda.ksdata.showSteps.append("bootloader")

            if self.appendLine:
                self.anaconda.bootloader.args.append(self.appendLine)

            if self.password:
                self.anaconda.bootloader.setPassword(self.password, isCrypted = self.isCrypted)

            if location != None:
                self.anaconda.bootloader.defaultDevice = location
            else:
                self.anaconda.bootloader.defaultDevice = -1

            if self.timeout:
                self.anaconda.bootloader.timeout = self.timeout

            # add unpartitioned devices that will get partitioned into
            # bootloader.drivelist
            disks = self.anaconda.storage.disks
            partitioned = self.anaconda.storage.partitioned
            for disk in [d for d in disks if not d.partitioned]:
                if shouldClear(disk, self.anaconda.storage.config.clearPartType,
                               self.anaconda.storage.config.clearPartDisks):
                    # add newly partitioned disks to the drivelist
                    self.anaconda.bootloader.drivelist.append(disk.name)
                elif disk.name in self.anaconda.bootloader.drivelist:
                    # remove unpartitioned disks from the drivelist
                    self.anaconda.bootloader.drivelist.remove(disk.name)
            self.anaconda.bootloader.drivelist.sort(
                cmp=self.anaconda.storage.compareDisks)

            # Throw out drives specified that don't exist.
            if self.driveorder and len(self.driveorder) > 0:
                new = []
                for drive in self.driveorder:
                    if drive in self.anaconda.bootloader.drivelist:
                        new.append(drive)
                    else:
                        log.warning("requested drive %s in boot drive order "
                                    "doesn't exist" %(drive,))

                self.anaconda.bootloader.updateDriveList(new)

        self.anaconda.ksdata.permanentSkipSteps.extend(["upgbootloader", "bootloader"])

class ClearPart(commands.clearpart.FC3_ClearPart):
    def parse(self, args):
        retval = commands.clearpart.FC3_ClearPart.parse(self, args)

        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        # Do any glob expansion now, since we need to have the real list of
        # disks available before the execute methods run.
        drives = []
        for spec in self.drives:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % spec)

        self.drives = drives

        return retval

    def execute(self):
        self.anaconda.storage.config.clearPartType = self.type
        self.anaconda.storage.config.clearPartDisks = self.drives
        if self.initAll:
            self.anaconda.storage.config.reinitializeDisks = self.initAll

        clearPartitions(self.anaconda.storage)
        self.anaconda.ksdata.skipSteps.append("cleardiskssel")

class Fcoe(commands.fcoe.F13_Fcoe):
    def parse(self, args):
        fc = commands.fcoe.F13_Fcoe.parse(self, args)

        if fc.nic not in isys.getDeviceProperties():
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent nic %s in fcoe command" % fc.nic)

        storage.fcoe.fcoe().addSan(nic=fc.nic, dcb=fc.dcb)

        return fc

class Firewall(commands.firewall.F14_Firewall):
    def execute(self):
        self.anaconda.firewall.enabled = self.enabled
        self.anaconda.firewall.trustdevs = self.trusts

        for port in self.ports:
            self.anaconda.firewall.portlist.append (port)

        for svc in self.services:
            self.anaconda.firewall.servicelist.append (svc)

class IgnoreDisk(commands.ignoredisk.RHEL6_IgnoreDisk):
    def parse(self, args):
        retval = commands.ignoredisk.RHEL6_IgnoreDisk.parse(self, args)

        # See comment in ClearPart.parse
        drives = []
        for spec in self.ignoredisk:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in ignoredisk command" % spec)

        self.ignoredisk = drives

        drives = []
        for spec in self.onlyuse:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in ignoredisk command" % spec)

        self.onlyuse = drives

        return retval

    def execute(self):
        if not self.interactive:
            self.anaconda.ksdata.skipSteps.extend(["filter", "filtertype"])

class Iscsi(commands.iscsi.F10_Iscsi):
    class Login(object):
        def __init__(self, iscsi_obj, tg_data):
            self.iscsi_obj = iscsi_obj
            self.tg_data = tg_data
        
        def login(self, node):
            (rc, _) = self.iscsi_obj.log_into_node(
                node, self.tg_data.user, self.tg_data.password,
                self.tg_data.user_in, self.tg_data.password_in)
            return rc

    def parse(self, args):
        tg = commands.iscsi.F10_Iscsi.parse(self, args)

        try:
            iscsi_obj = storage.iscsi.iscsi()
            discovered_nodes = iscsi_obj.discover(
                tg.ipaddr, tg.port, tg.user, tg.password, 
                tg.user_in, tg.password_in)
            login = self.Login(iscsi_obj, tg)
            logged_into_nodes = filter(login.login, discovered_nodes)
            if len(logged_into_nodes) < 1:
                msg = _("Could not log into any iSCSI nodes at the portal.")
                raise KickstartValueError, formatErrorMsg(self.lineno,
                                                          msg=msg)
        except (IOError, ValueError) as e:
            raise KickstartValueError, formatErrorMsg(self.lineno,
                                                      msg=str(e))

        return tg

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        retval = commands.iscsiname.FC6_IscsiName.parse(self, args)

        storage.iscsi.iscsi().initiator = self.iscsiname
        return retval

class Keyboard(commands.keyboard.FC3_Keyboard):
    def execute(self):
        self.anaconda.keyboard.set(self.keyboard)
        self.anaconda.keyboard.beenset = 1
        self.anaconda.ksdata.skipSteps.append("keyboard")

class Lang(commands.lang.FC3_Lang):
    def execute(self):
        self.anaconda.instLanguage.instLang = self.lang
        self.anaconda.instLanguage.systemLang = self.lang
        self.anaconda.ksdata.skipSteps.append("language")

class LogVolData(commands.logvol.F12_LogVolData):
    def execute(self):
        storage = self.anaconda.storage
        devicetree = storage.devicetree

        storage.doAutoPart = False

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
            if self.recommended:
                (self.size, self.maxSizeMB) = iutil.swapSuggestion()
                self.grow = True
        else:
            if self.fstype != "":
                type = self.fstype
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point \"%s\" is not valid." % (self.mountpoint,))

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.getDeviceByName(self.vgname)
        if not vg:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="No volume group exists with the name \"%s\".  Specify volume groups before logical volumes." % self.vgname)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.name:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --name")

            dev = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting logical volume with the name \"%s\" was found." % self.name)

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return

        # Make sure this LV name is not already used in the requested VG.
        if not self.preexist:
            tmp = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if tmp:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume name already used in volume group %s" % vg.name)

            # Size specification checks
            if not self.percent:
                if not self.size:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Size required")
                elif not self.grow and self.size*1024 < vg.peSize:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume size must be larger than the volume group physical extent size.")
            elif self.percent <= 0 or self.percent > 100:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Percentage must be between 0 and 100")

        # Now get a format to hold a lot of these extra values.
        format = getFormat(type,
                           mountpoint=self.mountpoint,
                           mountopts=self.fsopts)
        if not format:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if self.preexist:
            device = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent LV %s in logvol command" % self.name)

            removeExistingFormat(device, storage)
            devicetree.registerAction(ActionCreateFormat(device, format))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newLV(format=format,
                                    name=self.name,
                                    vg=vg,
                                    size=self.size,
                                    grow=self.grow,
                                    maxsize=self.maxSizeMB,
                                    percent=self.percent)

            if self.fsprofile and hasattr(request.format, "fsprofile"):
                request.format.fsprofile = self.fsprofile

            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
                storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(self.anaconda, self.escrowcert)
            if self.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Logging(commands.logging.FC6_Logging):
    def execute(self):
        if logger.tty_loglevel == DEFAULT_TTY_LEVEL:
            # not set from the command line
            level = logLevelMap[self.level]
            logger.tty_loglevel = level
            storage_log = logging.getLogger("storage")
            setHandlersLevel(log, level)
            setHandlersLevel(storage_log, level)

        if logger.remote_syslog == None and len(self.host) > 0:
            # not set from the command line, ok to use kickstart
            remote_server = self.host
            if self.port:
                remote_server = "%s:%s" %(self.host, self.port)
            logger.updateRemote(remote_server)

class NetworkData(commands.network.F8_NetworkData):
    def execute(self):
        if flags.imageInstall:
            if self.hostname != "":
                self.anaconda.network.setHostname(self.hostname)
                self.anaconda.network.overrideDHCPhostname = True

            # Only set hostname
            return

        devices = self.anaconda.network.netdevices

        if not self.device:
            if self.anaconda.network.ksdevice:
                msg = "ksdevice boot parameter"
                device = self.anaconda.network.ksdevice
            elif network.hasActiveNetDev():
                # device activated in stage 1 by network kickstart command
                msg = "first active device"
                device = network.getActiveNetDevs()[0]
            else:
                msg = "first device found"
                device = min(devices.keys())
            log.info("unspecified network --device in kickstart, using %s (%s)" %
                     (device, msg))
        else:
            device = self.device

        # If we were given a network device name, grab the device object.
        # If we were given a MAC address, resolve that to a device name
        # and then grab the device object.  Otherwise, errors.
        dev = None

        if devices.has_key(device):
            dev = devices[device]
        else:
            for (key, val) in devices.iteritems():
                if val.get("HWADDR").lower() == device.lower():
                    dev = val
                    break

        if self.hostname != "":
            self.anaconda.network.setHostname(self.hostname)
            self.anaconda.network.overrideDHCPhostname = True
            if not dev:
                # Only set hostname
                return
        else:
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="The provided network interface %s does not exist" % device)


        # ipv4 settings
        if not self.noipv4:
            dev.set(("BOOTPROTO", self.bootProto))
            dev.set(("DHCPCLASS", self.dhcpclass))

            if self.bootProto == "static":
                if (self.ip):
                    dev.set(("IPADDR", self.ip))
                if (self.netmask):
                    dev.set(("NETMASK", self.netmask))

        # ipv6 settings
        if self.noipv6:
            dev.set(("IPV6INIT", "no"))
        else:
            dev.set(("IPV6INIT", "yes"))
            if self.ipv6 == "auto":
                dev.set(("IPV6_AUTOCONF", "yes"))
            elif self.ipv6 == "dhcp":
                dev.set(("IPV6_AUTOCONF", "no"))
                dev.set(("DHCPV6C", "yes"))
            elif self.ipv6:
                dev.set(("IPV6_AUTOCONF", "no"))
                dev.set(("IPV6ADDR", "%s" % self.ipv6))
        # settings common for ipv4 and ipv6
        if not self.noipv6 or not self.noipv4:
            if self.onboot:
                dev.set (("ONBOOT", "yes"))
            else:
                dev.set (("ONBOOT", "no"))

            if self.ethtool:
                dev.set(("ETHTOOL_OPTS", self.ethtool))

            if isys.isWirelessDevice(device):
                if self.essid:
                    dev.set(("ESSID", self.essid))
                if self.wepkey:
                    dev.set(("DEFAULTKEY", "1"))
                    dev.wepkey = self.wepkey
                    dev.writeWepkeyFile()

            if self.nameserver != "":
                self.anaconda.network.setDNS(self.nameserver, device)

            if self.gateway != "":
                self.anaconda.network.setGateway(self.gateway, device)

        needs_net = (self.anaconda.methodstr and
                     (self.anaconda.methodstr.startswith("http:") or
                      self.anaconda.methodstr.startswith("ftp:") or
                      self.anaconda.methodstr.startswith("nfs:")))
        # First kickstart network command wins
        # TODORV: document
        if needs_net and not network.hasActiveNetDev():
            log.info("Bringing up network device %s in stage2 kickstart ..." %
                     device)
            dev.set (("onboot", "yes"))
            rc = self.anaconda.network.bringUp()
            log.info("Network setup %s" % (rc and 'succeeded' or 'failed',))

class MultiPath(commands.multipath.FC6_MultiPath):
    def parse(self, args):
        raise NotImplementedError("The multipath kickstart command is not currently supported")

class DmRaid(commands.dmraid.FC6_DmRaid):
    def parse(self, args):
        raise NotImplementedError("The dmraid kickstart command is not currently supported")

class PartitionData(commands.partition.F12_PartData):
    def execute(self):
        storage = self.anaconda.storage
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if self.onbiosdisk != "":
            for (disk, biosdisk) in storage.eddDict.iteritems():
                if str(biosdisk) == self.onbiosdisk:
                    self.disk = disk
                    break

            if self.disk == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified BIOS disk %s cannot be determined" % self.onbiosdisk)

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
            if self.recommended:
                (self.size, self.maxSizeMB) = iutil.swapSuggestion()
                self.grow = True
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif self.mountpoint == "None":
            self.mountpoint = ""
            if self.fstype:
                type = self.fstype
            else:
                type = storage.defaultFSType
        elif self.mountpoint == 'appleboot':
            type = "Apple Bootstrap"
            self.mountpoint = ""
            kwargs["weight"] = self.anaconda.platform.weight(fstype="appleboot")
        elif self.mountpoint == 'prepboot':
            type = "PPC PReP Boot"
            self.mountpoint = ""
            kwargs["weight"] = self.anaconda.platform.weight(fstype="prepboot")
        elif self.mountpoint.startswith("raid."):
            type = "mdmember"
            kwargs["name"] = self.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID partition defined multiple times")

            if self.grow:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--grow is not supported for RAID partitions")

            # store "raid." alias for other ks partitioning commands
            if self.onPart:
                self.anaconda.ksdata.onPart[kwargs["name"]] = self.onPart
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            # store "pv." alias for other ks partitioning commands
            if self.onPart:
                self.anaconda.ksdata.onPart[kwargs["name"]] = self.onPart
            self.mountpoint = ""
        elif self.mountpoint == "/boot/efi":
            type = "EFI System Partition"
            self.fsopts = "defaults,uid=0,gid=0,umask=0077,shortname=winnt"
            kwargs["weight"] = self.anaconda.platform.weight(fstype="efi")
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot":
                type = self.anaconda.platform.defaultBootFSType
            else:
                type = storage.defaultFSType

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.onPart:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --onpart")

            dev = devicetree.getDeviceByName(udev_resolve_devspec(self.onPart))
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting partition with the name \"%s\" was found." % self.onPart)

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     mountpoint=self.mountpoint,
                                     label=self.label,
                                     mountopts=self.fsopts)
        if not kwargs["format"]:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a specific disk to create the partition on, verify
        # that it exists first.  If it doesn't exist, see if it exists with
        # mapper/ on the front.  If that doesn't exist either, it's an error.
        if self.disk:
            names = [self.disk, "mapper/" + self.disk]
            for n in names:
                disk = devicetree.getDeviceByName(udev_resolve_devspec(n))
                if not disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % n)

                should_clear = shouldClear(disk,
                                           storage.config.clearPartType,
                                           storage.config.clearPartDisks)
                if disk and (disk.partitioned or should_clear):
                    kwargs["disks"] = [disk]
                    break
                elif disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified unpartitioned disk %s in partition command" % self.disk)

            if not kwargs["disks"]:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % self.disk)

        kwargs["grow"] = self.grow
        kwargs["size"] = self.size
        kwargs["maxsize"] = self.maxSizeMB
        kwargs["primary"] = self.primOnly

        # If we were given a pre-existing partition to create a filesystem on,
        # we need to verify it exists and then schedule a new format action to
        # take place there.  Also, we only support a subset of all the options
        # on pre-existing partitions.
        if self.onPart:
            device = devicetree.getDeviceByName(udev_resolve_devspec(self.onPart))
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent partition %s in partition command" % self.onPart)

            removeExistingFormat(device, storage)
            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newPartition(**kwargs)

            if self.fsprofile and hasattr(request.format, "fsprofile"):
                request.format.fsprofile = self.fsprofile

            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(self.anaconda, self.escrowcert)
            if self.onPart:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Reboot(commands.reboot.FC6_Reboot):
    def execute(self):
        self.anaconda.ksdata.skipSteps.append("complete")

class RaidData(commands.raid.F12_RaidData):
    def execute(self):
        raidmems = []
        devicename = "md%d" % self.device

        storage = self.anaconda.storage
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint
            self.anaconda.ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            self.mountpoint = ""
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot" and self.anaconda.platform.supportsMdRaidBoot:
                type = self.anaconda.platform.defaultBootFSType
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point is not valid.")

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not devicename:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --device")

            dev = devicetree.getDeviceByName(devicename)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting RAID device with the name \"%s\" was found." % devicename)

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return

        # Get a list of all the RAID members.
        for member in self.members:
            # if member is using --onpart, use original device
            member = self.anaconda.ksdata.onPart.get(member, member)
            dev = devicetree.getDeviceByName(member)
            if dev and dev.format.type == "luks":
                try:
                    dev = devicetree.getChildren(dev)[0]
                except IndexError:
                    dev = None
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in RAID specification" % member)

            raidmems.append(dev)

        if not self.preexist:
            if len(raidmems) == 0:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without any RAID members")

            if self.level == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without RAID level")

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     mountpoint=self.mountpoint,
                                     mountopts=self.fsopts)
        if not kwargs["format"]:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        kwargs["name"] = devicename
        kwargs["level"] = self.level
        kwargs["parents"] = raidmems
        kwargs["memberDevices"] = len(raidmems)
        kwargs["totalDevices"] = kwargs["memberDevices"]+self.spares

        # If we were given a pre-existing RAID to create a filesystem on,
        # we need to verify it exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing RAIDs.
        if self.preexist:
            device = devicetree.getDeviceByName(devicename)
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specifeid nonexistent RAID %s in raid command" % devicename)

            removeExistingFormat(device, storage)
            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            try:
                request = storage.newMDArray(**kwargs)
            except ValueError, e:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg=str(e))

            if self.fsprofile and hasattr(request.format, "fsprofile"):
                request.format.fsprofile = self.fsprofile

            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(self.anaconda, self.escrowcert)
            if self.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.anaconda.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class RootPw(commands.rootpw.F8_RootPw):
    def execute(self):
        self.anaconda.users.rootPassword["password"] = self.password
        self.anaconda.users.rootPassword["isCrypted"] = self.isCrypted
        self.anaconda.users.rootPassword["lock"] = self.lock
        self.anaconda.ksdata.skipSteps.append("accounts")

class SELinux(commands.selinux.FC3_SELinux):
    def execute(self):
        self.anaconda.security.setSELinux(self.selinux)

class SkipX(commands.skipx.FC3_SkipX):
    def execute(self):
        if self.anaconda.desktop is not None:
            self.anaconda.desktop.setDefaultRunLevel(3)

class Timezone(commands.timezone.FC6_Timezone):
    def execute(self):
        # check validity
        tab = zonetab.ZoneTab()
        if self.timezone not in (entry.tz.replace(' ','_') for entry in
                                 tab.getEntries()):
            log.warning("Timezone %s set in kickstart is not valid." % (self.timezone,))

        self.anaconda.timezone.setTimezoneInfo(self.timezone, self.isUtc)
        self.anaconda.ksdata.skipSteps.append("timezone")

class Upgrade(commands.upgrade.F11_Upgrade):
    def execute(self):
        self.anaconda.upgrade = self.upgrade

class VolGroupData(commands.volgroup.FC3_VolGroupData):
    def execute(self):
        pvs = []

        storage = self.anaconda.storage
        devicetree = storage.devicetree

        storage.doAutoPart = False

        # Get a list of all the physical volume devices that make up this VG.
        for pv in self.physvols:
            # if pv is using --onpart, use original device
            pv = self.anaconda.ksdata.onPart.get(pv, pv)
            dev = devicetree.getDeviceByName(pv)
            if dev and dev.format.type == "luks":
                try:
                    dev = devicetree.getChildren(dev)[0]
                except IndexError:
                    dev = None
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in Volume Group specification" % pv)

            pvs.append(dev)

        if len(pvs) == 0 and not self.preexist:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group defined without any physical volumes.  Either specify physical volumes or use --useexisting.")

        if self.pesize not in getPossiblePhysicalExtents(floor=1024):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group specified invalid pesize")

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not self.format or self.preexist:
            if not self.vgname:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat or --useexisting used without giving a name")

            dev = devicetree.getDeviceByName(self.vgname)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting VG with the name \"%s\" was found." % self.vgname)
        else:
            request = storage.newVG(pvs=pvs,
                                    name=self.vgname,
                                    peSize=self.pesize/1024.0)

            storage.createDevice(request)

class XConfig(commands.xconfig.F14_XConfig):
    def execute(self):
        if self.startX:
            self.anaconda.desktop.setDefaultRunLevel(5)

        if self.defaultdesktop:
            self.anaconda.desktop.setDefaultDesktop(self.defaultdesktop)

class ZFCP(commands.zfcp.F14_ZFCP):
    def parse(self, args):
        fcp = commands.zfcp.F14_ZFCP.parse(self, args)
        try:
            storage.zfcp.ZFCP().addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)
        except ValueError, e:
            log.warning(str(e))

        return fcp

###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
commandMap = {
        "auth": Authconfig,
        "authconfig": Authconfig,
        "autopart": AutoPart,
        "autostep": AutoStep,
        "bootloader": Bootloader,
        "clearpart": ClearPart,
        "dmraid": DmRaid,
        "fcoe": Fcoe,
        "firewall": Firewall,
        "halt": Reboot,
        "ignoredisk": IgnoreDisk,
        "install": Upgrade,
        "iscsi": Iscsi,
        "iscsiname": IscsiName,
        "keyboard": Keyboard,
        "lang": Lang,
        "logging": Logging,
        "multipath": MultiPath,
        "poweroff": Reboot,
        "reboot": Reboot,
        "rootpw": RootPw,
        "selinux": SELinux,
        "shutdown": Reboot,
        "skipx": SkipX,
        "timezone": Timezone,
        "upgrade": Upgrade,
        "xconfig": XConfig,
        "zfcp": ZFCP,
}

dataMap = {
        "LogVolData": LogVolData,
        "NetworkData": NetworkData,
        "PartData": PartitionData,
        "RaidData": RaidData,
        "VolGroupData": VolGroupData,
}

superclass = returnClassForVersion()

class AnacondaKSHandler(superclass):
    def __init__ (self, anaconda):
        superclass.__init__(self, commandUpdates=commandMap, dataUpdates=dataMap)
        self.packages = AnacondaKSPackages()

        self.permanentSkipSteps = []
        self.skipSteps = []
        self.showSteps = []
        self.anaconda = anaconda
        self.onPart = {}

        # All the KickstartCommand and KickstartData objects that
        # handleCommand returns, so we can later iterate over them and run
        # the execute methods.  These really should be stored in the order
        # they're seen in the kickstart file.
        self._dataObjs = []

    def add(self, obj):
        if isinstance(obj, KickstartCommand):
            # Commands can only be run once, and the latest one seen takes
            # precedence over any earlier ones.
            i = 0
            while i < len(self._dataObjs):
                if self._dataObjs[i].__class__ == obj.__class__:
                    self._dataObjs.pop(i)
                    break

                i += 1

            self._dataObjs.append(obj)
        else:
            # Data objects can be seen over and over again.
            self._dataObjs.append(obj)

    def dispatcher(self, args, lineno):
        cmd = args[0]

        if self.commands.has_key(cmd):
            self.commands[cmd].anaconda = self.anaconda

        return superclass.dispatcher(self, args, lineno)

    def execute(self):
        try:
            for obj in filter(lambda o: hasattr(o, "execute"), self._dataObjs):
                obj.anaconda = self.anaconda
                obj.execute()
        except KickstartError as e:
            if self.anaconda.intf:
                self.anaconda.intf.kickstartErrorWindow(e.__str__())
                sys.exit(1)
            else:
                stderrLog.critical(_("The following error was found while parsing the kickstart "
                                     "configuration file:\n\n%s") % e)
                sys.exit(1)

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler, missingIncludeIsFatal=False)

    def addScript (self):
        if self._script["type"] != KS_SCRIPT_PRE:
            return

        s = AnacondaKSScript (self._script["body"], type=self._script["type"],
                              interp=self._script["interp"],
                              lineno=self._script["lineno"],
                              inChroot=self._script["chroot"],
                              logfile=self._script["log"],
                              errorOnFail=self._script["errorOnFail"])
        self.handler.scripts.append(s)

    def addPackages (self, line):
        pass

    def handleCommand (self, lineno, args):
        pass

    def handlePackageHdr (self, lineno, args):
        pass

    def handleScriptHdr (self, lineno, args):
        if not args[0] == "%pre":
            return

        KickstartParser.handleScriptHdr(self, lineno, args)

class AnacondaKSParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler)

    def addScript (self):
        if string.join(self._script["body"]).strip() == "":
            return

        s = AnacondaKSScript (self._script["body"], type=self._script["type"],
                              interp=self._script["interp"],
                              lineno=self._script["lineno"],
                              inChroot=self._script["chroot"],
                              logfile=self._script["log"],
                              errorOnFail=self._script["errorOnFail"])
        self.handler.scripts.append(s)

    def handlePackageHdr (self, lineno, args):
        KickstartParser.handlePackageHdr (self, lineno, args)
        self.handler.packages.seen = True

    def handleCommand (self, lineno, args):
        if not self.handler:
            return

        retval = KickstartParser.handleCommand(self, lineno, args)
        self.handler.add(retval)
        return retval

def preScriptPass(anaconda, file):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler(anaconda))

    try:
        ksparser.readKickstart(file)
    except (KickstartValueError, KickstartParseError) as e:
       if anaconda.intf:
           anaconda.intf.kickstartErrorWindow(e.__str__())
           sys.exit(1)
       else:
            stderrLog.critical(_("The following error was found while parsing the kickstart "
                              "configuration file:\n\n%s") % e)
            sys.exit(1)
    except KickstartError as e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % file)
            sys.exit(1)
        else:
            stderrLog.critical(_("The following error was found while parsing the kickstart "
                              "configuration file:\n\n%s") % e)
            sys.exit(1)

    # run %pre scripts
    runPreScripts(anaconda, ksparser.handler.scripts)

def parseKickstart(anaconda, file):
    try:
        file = preprocessKickstart(file)
    except KickstartError, msg:
        stderrLog.critical(_("Error processing %%ksappend lines: %s") % msg)
        sys.exit(1)
    except Exception, e:
        stderrLog.critical(_("Unknown error processing %%ksappend lines: %s") % e)
        sys.exit(1)

    handler = AnacondaKSHandler(anaconda)
    ksparser = AnacondaKSParser(handler)

    # We need this so all the /dev/disk/* stuff is set up before parsing.
    udev_trigger(subsystem="block", action="change")
    # So that drives onlined by these can be used in the ks file
    storage.iscsi.iscsi().startup()
    storage.fcoe.fcoe().startup()
    storage.zfcp.ZFCP().startup()
    # Note we do NOT call dasd.startup() here, that does not online drives, but
    # only checks if they need formatting, which requires zerombr to be known

    try:
        ksparser.readKickstart(file)
    except (KickstartValueError, KickstartParseError) as e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(e.__str__())
            sys.exit(1)
        else:
            stderrLog.critical(_("The following error was found while parsing the kickstart "
                              "configuration file:\n\n%s") % e)
            sys.exit(1)
    except KickstartError as e:
        # We may not have an intf now, but we can do better than just raising
        # the exception.
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % file)
            sys.exit(1)
        else:
            stderrLog.critical(_("The following error was found while parsing the kickstart "
                              "configuration file:\n\n%s") % e)
            sys.exit(1)

    return handler

def runPostScripts(anaconda):
    if not anaconda.ksdata:
        return

    postScripts = filter (lambda s: s.type == KS_SCRIPT_POST,
                          anaconda.ksdata.scripts)

    if len(postScripts) == 0:
        return

    # Remove environment variables that cause problems for %post scripts.
    for var in ["LIBUSER_CONF"]:
        if os.environ.has_key(var):
            del(os.environ[var])

    log.info("Running kickstart %%post script(s)")
    if anaconda.intf is not None:
        w = anaconda.intf.waitWindow(_("Post-Installation"),
                            _("Running post-installation scripts"))
        
    map (lambda s: s.run(anaconda.rootPath, flags.serial, anaconda.intf), postScripts)

    log.info("All kickstart %%post script(s) have been run")
    if anaconda.intf is not None:
        w.pop()

def runPreScripts(anaconda, scripts):
    preScripts = filter (lambda s: s.type == KS_SCRIPT_PRE, scripts)

    if len(preScripts) == 0:
        return

    log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    map (lambda s: s.run("/", flags.serial, anaconda.intf), preScripts)

    log.info("All kickstart %%pre script(s) have been run")

def runTracebackScripts(anaconda):
    log.info("Running kickstart %%traceback script(s)")
    for script in filter (lambda s: s.type == KS_SCRIPT_TRACEBACK,
                          anaconda.ksdata.scripts):
        script.run("/", flags.serial)
    log.info("All kickstart %%traceback script(s) have been run")

def selectPackages(anaconda):
    ksdata = anaconda.ksdata
    ignoreAll = False

    # If no %packages header was seen, use the installclass's default group
    # selections.  This can also be explicitly specified with %packages
    # --default.  Otherwise, select whatever was given (even if it's nothing).
    if not ksdata.packages.seen or ksdata.packages.default:
        anaconda.instClass.setGroupSelection(anaconda)
        if not ksdata.packages.seen:
            return

    for pkg in ksdata.packages.packageList:
        num = anaconda.backend.selectPackage(pkg)
        if ksdata.packages.handleMissing == KS_MISSING_IGNORE or ignoreAll:
            continue
        if num > 0:
            continue
        rc = anaconda.intf.messageWindow(_("Missing Package"),
                                _("You have specified that the "
                                  "package '%s' should be installed.  "
                                  "This package does not exist. "
                                  "Would you like to continue or "
                                  "abort this installation?") %(pkg,),
                                type="custom",
                                custom_buttons=[_("_Abort"),
                                                _("_Ignore All"),
                                                _("_Continue")])
        if rc == 0:
            sys.exit(1)
        elif rc == 1:
            ignoreAll = True

    ksdata.packages.groupList.insert(0, Group("Core"))

    if ksdata.packages.addBase:
        ksdata.packages.groupList.insert(1, Group("Base"))
    else:
        log.warning("not adding Base group")

    for grp in ksdata.packages.groupList:
        default = False
        optional = False

        if grp.include == GROUP_DEFAULT:
            default = True
        elif grp.include == GROUP_ALL:
            default = True
            optional = True

        try:
            anaconda.backend.selectGroup(grp.name, (default, optional))
        except NoSuchGroup, e:
            if ksdata.packages.handleMissing == KS_MISSING_IGNORE or ignoreAll:
                pass
            else:
                rc = anaconda.intf.messageWindow(_("Missing Group"),
                                        _("You have specified that the "
                                          "group '%s' should be installed. "
                                          "This group does not exist. "
                                          "Would you like to continue or "
                                          "abort this installation?")
                                        %(grp.name,),
                                        type="custom",
                                        custom_buttons=[_("_Abort"),
                                                        _("_Ignore All"),
                                                        _("_Continue")])
                if rc == 0:
                    sys.exit(1)
                elif rc == 1:
                    ignoreAll = True

    map(anaconda.backend.deselectPackage, ksdata.packages.excludedList)
    map(lambda g: anaconda.backend.deselectGroup(g.name),
        ksdata.packages.excludedGroupList)

def setSteps(anaconda):
    def havePackages(packages):
        return len(packages.groupList) > 0 or len(packages.packageList) > 0 or \
               len(packages.excludedList) > 0 or len(packages.excludedGroupList) > 0

    dispatch = anaconda.dispatch
    ksdata = anaconda.ksdata

    if ksdata.upgrade.upgrade:
        upgrade.setSteps(anaconda)

        # we have no way to specify migrating yet
        dispatch.skipStep("upgrademigfind")
        dispatch.skipStep("upgrademigratefs")
        dispatch.skipStep("upgradecontinue")
        dispatch.skipStep("findinstall", permanent = 1)
        dispatch.skipStep("language")
        dispatch.skipStep("keyboard")
        dispatch.skipStep("betanag")
    else:
        anaconda.instClass.setSteps(anaconda)
        dispatch.skipStep("findrootparts")

    dispatch.skipStep("betanag")
    dispatch.skipStep("network")

    # Storage is initialized for us right when kickstart processing starts.
    dispatch.skipStep("storageinit")

    if not anaconda.storage.config.ignoreDiskInteractive:
        # Since ignoredisk is optional and not specifying it means you want to
        # consider all possible disks, we should not stop on the filter steps
        # unless we've been told to.
        dispatch.skipStep("filter")
        dispatch.skipStep("filtertype")

    # Make sure to automatically reboot if told to.
    if ksdata.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
        dispatch.skipStep("complete")

    # If the package section included anything, skip group selection.
    if ksdata.upgrade.upgrade:
        ksdata.skipSteps.extend(["tasksel", "group-selection"])

        # Special check for this, since it doesn't make any sense.
        if ksdata.packages.seen:
            warnings.warn("Ignoring contents of %packages section due to upgrade.")
    elif havePackages(ksdata.packages):
        ksdata.skipSteps.extend(["tasksel", "group-selection"])
    else:
        if ksdata.packages.seen:
            ksdata.skipSteps.extend(["tasksel", "group-selection"])
        else:
            ksdata.showSteps.extend(["tasksel", "group-selection"])

    for n in ksdata.skipSteps:
        dispatch.skipStep(n)
    for n in ksdata.permanentSkipSteps:
        dispatch.skipStep(n, permanent=1)
    for n in ksdata.showSteps:
        dispatch.skipStep(n, skip = 0)

    # Text mode doesn't have all the steps that graphical mode does, so we
    # can't stop and prompt for missing information.  Make sure we've got
    # everything that would be provided by a missing section now and error
    # out if we don't.
    if anaconda.displayMode == "t":
        missingSteps = [("bootloader", "Bootloader configuration"),
                        ("filter", "Disks to use in installation"),
                        ("cleardiskssel", "Disks to clear"),
                        ("group-selection", "Package selection")]
        errors = []

        for (step, msg) in missingSteps:
            if not dispatch.stepInSkipList(step):
                errors.append(msg)

        if len(errors) > 0:
            anaconda.intf.kickstartErrorWindow(_("The kickstart configuration "
                "file is missing required information that anaconda cannot "
                "prompt for.  Please add the following sections and try "
                "again:\n%s") % ", ".join(errors))
            sys.exit(0)
