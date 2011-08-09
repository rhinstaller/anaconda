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
from storage.devicelibs.mpath import MultipathConfigWriter, identifyMultipaths
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
storage_log = logging.getLogger("storage")
stdoutLog = logging.getLogger("anaconda.stdout")
from anaconda_log import logger, logLevelMap, setHandlersLevel

# deviceMatches is called early, before any multipaths can possibly be coalesced
# so it needs to know about them in some additional way
multipaths = None

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

    if url in anaconda.id.escrowCertificates:
        return anaconda.id.escrowCertificates[url]

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
        urlgrabber.grabber.reset_curl_obj()

    log.info("escrow: downloading %s" % (url,))

    try:
        f = urlgrabber.urlopen(url)
    except urlgrabber.grabber.URLGrabError as e:
        msg = _("The following error was encountered while downloading the escrow certificate:\n\n%s" % e)
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(msg)
            sys.exit(1)
        else:
            stdoutLog.critical(msg)
            sys.exit(1)

    try:
        anaconda.id.escrowCertificates[url] = f.read()
    finally:
        f.close()

    return anaconda.id.escrowCertificates[url]

def detect_multipaths():
    global multipaths
    mcw = MultipathConfigWriter()
    cfg = mcw.write(friendly_names=True)
    with open("/etc/multipath.conf", "w+") as mpath_cfg:
        mpath_cfg.write(cfg)
    devices = udev_get_block_devices()
    (singles, multipaths, partitions) = identifyMultipaths(devices)

def deviceMatches(spec):
    full_spec = spec
    if not full_spec.startswith("/dev/"):
        full_spec = os.path.normpath("/dev/" + full_spec)

    # the regular case
    matches = udev_resolve_glob(full_spec)
    dev = udev_resolve_devspec(full_spec)
    # udev_resolve_devspec returns None if there's no match, but we don't
    # want that ending up in the list.
    if dev and dev not in matches:
        matches.append(dev)

    # now see if any mpaths and mpath members match
    for members in multipaths:
        mpath_name = udev_device_get_multipath_name(members[0])
        member_names = map(udev_device_get_name, members)
        if mpath_name == spec or (dev in member_names):
            # append the entire mpath
            matches.append(mpath_name)
            matches.extend(member_names)

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
    def execute(self, anaconda):
        anaconda.id.auth = self.authconfig

class AutoPart(commands.autopart.F12_AutoPart):
    def execute(self, anaconda):
        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        anaconda.id.instClass.setDefaultPartitioning(anaconda.id.storage, anaconda.platform)
        anaconda.id.storage.doAutoPart = True

        if self.encrypted:
            anaconda.id.storage.encryptedAutoPart = True
            anaconda.id.storage.encryptionPassphrase = self.passphrase
            anaconda.id.storage.autoPartEscrowCert = \
                getEscrowCertificate(anaconda, self.escrowcert)
            anaconda.id.storage.autoPartAddBackupPassphrase = \
                self.backuppassphrase

        anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class AutoStep(commands.autostep.FC3_AutoStep):
    def execute(self, anaconda):
        flags.autostep = 1
        flags.autoscreenshot = self.autoscreenshot

class Bootloader(commands.bootloader.RHEL6_Bootloader):
    def execute(self, anaconda):
        if self.location == "none":
            location = None
        elif self.location == "partition":
            location = "boot"
        else:
            location = self.location

        if self.upgrade and not anaconda.id.getUpgrade():
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Selected upgrade mode for bootloader but not doing an upgrade")

        if self.upgrade:
            anaconda.id.bootloader.kickstart = 1
            anaconda.id.bootloader.doUpgradeOnly = 1

        if location is None:
            anaconda.id.ksdata.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            anaconda.id.ksdata.showSteps.append("bootloader")

            if self.appendLine:
                anaconda.id.bootloader.args.append(self.appendLine)

            if self.password:
                anaconda.id.bootloader.setPassword(self.password, isCrypted = self.isCrypted)

            if location != None:
                anaconda.id.bootloader.defaultDevice = location
            else:
                anaconda.id.bootloader.defaultDevice = -1

            if self.timeout:
                anaconda.id.bootloader.timeout = self.timeout

            # add unpartitioned devices that will get partitioned into
            # bootloader.drivelist
            disks = anaconda.id.storage.disks
            partitioned = anaconda.id.storage.partitioned
            for disk in [d for d in disks if not d.partitioned]:
                if shouldClear(disk, anaconda.id.storage.clearPartType,
                               anaconda.id.storage.clearPartDisks):
                    # add newly partitioned disks to the drivelist
                    anaconda.id.bootloader.drivelist.append(disk.name)
                elif disk.name in anaconda.id.bootloader.drivelist:
                    # remove unpartitioned disks from the drivelist
                    anaconda.id.bootloader.drivelist.remove(disk.name)
            anaconda.id.bootloader.drivelist.sort(
                cmp=anaconda.id.storage.compareDisks)

            # Throw out drives specified that don't exist.
            if self.driveorder and len(self.driveorder) > 0:
                new = []
                for drive in self.driveorder:
                    if drive in anaconda.id.bootloader.drivelist:
                        new.append(drive)
                    else:
                        log.warning("requested drive %s in boot drive order "
                                    "doesn't exist" %(drive,))

                anaconda.id.bootloader.updateDriveList(new)

        anaconda.id.ksdata.permanentSkipSteps.extend(["upgbootloader", "bootloader"])
        anaconda.id.ksdata.skipOnTextInteractive.extend(["upgbootloader", "bootloader"])

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

    def execute(self, anaconda):
        anaconda.id.storage.clearPartType = self.type
        anaconda.id.storage.clearPartDisks = self.drives
        if self.initAll:
            anaconda.id.storage.reinitializeDisks = self.initAll

        clearPartitions(anaconda.id.storage)
        anaconda.id.ksdata.skipSteps.append("cleardiskssel")
        anaconda.id.ksdata.skipOnTextInteractive.append("cleardiskssel")

class Fcoe(commands.fcoe.F13_Fcoe):
    def parse(self, args):
        fc = commands.fcoe.F13_Fcoe.parse(self, args)

        if fc.nic not in isys.getDeviceProperties():
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent nic %s in fcoe command" % fc.nic)

        storage.fcoe.fcoe().addSan(nic=fc.nic, dcb=fc.dcb)

        return fc

class Firewall(commands.firewall.F10_Firewall):
    def execute(self, anaconda):
        anaconda.id.firewall.enabled = self.enabled
        anaconda.id.firewall.trustdevs = self.trusts

        for port in self.ports:
            anaconda.id.firewall.portlist.append (port)

        for svc in self.services:
            anaconda.id.firewall.servicelist.append (svc)

class Firstboot(commands.firstboot.FC3_Firstboot):
    def execute(self, anaconda):
        anaconda.id.firstboot = self.firstboot

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

    def execute(self, anaconda):
        anaconda.id.storage.ignoreDiskInteractive = self.interactive
        anaconda.id.storage.ignoredDisks = self.ignoredisk
        anaconda.id.storage.exclusiveDisks = self.onlyuse

        if self.interactive:
            anaconda.id.ksdata.skipOnTextInteractive.extend(["filter", "filtertype"])
        else:
            anaconda.id.ksdata.skipSteps.extend(["filter", "filtertype"])

class Iscsi(commands.iscsi.F10_Iscsi):
    def parse(self, args):
        tg = commands.iscsi.F10_Iscsi.parse(self, args)

        try:
            storage.iscsi.iscsi().addTarget(tg.ipaddr, tg.port, tg.user,
                                            tg.password, tg.user_in,
                                            tg.password_in,
                                            target=tg.target)
            log.info("added iscsi target: %s" %(tg.ipaddr,))
        except (IOError, ValueError), e:
            raise KickstartValueError, formatErrorMsg(self.lineno,
                                                      msg=str(e))
        return tg

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        retval = commands.iscsiname.FC6_IscsiName.parse(self, args)

        storage.iscsi.iscsi().initiator = self.iscsiname
        return retval

class Keyboard(commands.keyboard.FC3_Keyboard):
    def execute(self, anaconda):
        anaconda.id.keyboard.set(self.keyboard)
        anaconda.id.keyboard.beenset = 1
        anaconda.id.ksdata.skipSteps.append("keyboard")

class Lang(commands.lang.FC3_Lang):
    def execute(self, anaconda):
        anaconda.id.instLanguage.instLang = self.lang
        anaconda.id.instLanguage.systemLang = self.lang
        anaconda.id.ksdata.skipSteps.append("language")

class LogVolData(commands.logvol.F12_LogVolData):
    def execute(self, anaconda):
        storage = anaconda.id.storage
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
            anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
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

            cert = getEscrowCertificate(anaconda, self.escrowcert)
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

        anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Logging(commands.logging.FC6_Logging):
    def execute(self, anaconda):
        setHandlersLevel(log, logLevelMap[self.level])

        if self.host != "" and self.port != "":
            logger.addSysLogHandler(log, self.host, port=int(self.port))
        elif self.host != "":
            logger.addSysLogHandler(log, self.host)

class NetworkData(commands.network.RHEL6_NetworkData):
    def execute(self, anaconda):

        devices = anaconda.id.network.netdevices

        if not self.device:
            if anaconda.id.network.ksdevice:
                msg = "ksdevice boot parameter"
                device = anaconda.id.network.ksdevice
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
            if self.device.lower() == "ibft":
                return
            if self.device.lower() == "bootif":
                if "BOOTIF" in flags.cmdline:
                    # MAC address like 01-aa-bb-cc-dd-ee-ff
                    device = flags.cmdline["BOOTIF"][3:]
                    device = device.replace("-",":")
                else:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Using --device=bootif without BOOTIF= boot option supplied")
            else: device = self.device

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
            anaconda.id.network.setHostname(self.hostname)
            anaconda.id.network.overrideDHCPhostname = True
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

            if self.mtu:
                dev.set(("MTU", self.mtu))

            if self.ethtool:
                dev.set(("ETHTOOL_OPTS", self.ethtool))

        if self.nameserver != "":
            anaconda.id.network.setDNS(self.nameserver, dev.iface)

        if self.gateway != "":
            anaconda.id.network.setGateway(self.gateway, dev.iface)

        if self.nodefroute:
            dev.set (("DEFROUTE", "no"))

        needs_net = (anaconda.methodstr and
                     (anaconda.methodstr.startswith("http:") or
                      anaconda.methodstr.startswith("ftp:") or
                      anaconda.methodstr.startswith("nfs:")))
        # First kickstart network command wins
        # TODORV: document
        if needs_net and not network.hasActiveNetDev():
            log.info("Bringing up network device %s in stage2 kickstart ..." %
                     dev.iface)
            dev.set (("onboot", "yes"))
            rc = anaconda.id.network.bringUp()
            log.info("Network setup %s" % (rc and 'succeeded' or 'failed',))

class MultiPath(commands.multipath.FC6_MultiPath):
    def parse(self, args):
        raise NotImplementedError("The multipath kickstart command is not currently supported")

class DmRaid(commands.dmraid.FC6_DmRaid):
    def parse(self, args):
        raise NotImplementedError("The dmraid kickstart command is not currently supported")

class PartitionData(commands.partition.F12_PartData):
    def execute(self, anaconda):
        storage = anaconda.id.storage
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
            kwargs["weight"] = anaconda.platform.weight(fstype="appleboot")
        elif self.mountpoint == 'prepboot':
            type = "PPC PReP Boot"
            self.mountpoint = ""
            kwargs["weight"] = anaconda.platform.weight(fstype="prepboot")
        elif self.mountpoint.startswith("raid."):
            type = "mdmember"
            kwargs["name"] = self.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID partition defined multiple times")

            # store "raid." alias for other ks partitioning commands
            if self.onPart:
                anaconda.id.ksdata.onPart[kwargs["name"]] = self.onPart
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            # store "pv." alias for other ks partitioning commands
            if self.onPart:
                anaconda.id.ksdata.onPart[kwargs["name"]] = self.onPart
            self.mountpoint = ""
        elif self.mountpoint == "/boot/efi":
            type = "EFI System Partition"
            self.fsopts = "defaults,uid=0,gid=0,umask=0077,shortname=winnt"
            kwargs["weight"] = anaconda.platform.weight(fstype="efi")
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot":
                type = anaconda.platform.defaultBootFSType
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
            anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return

        # Size specification checks.
        if not self.size and not self.onPart:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Partition requires a size specification")

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
                # if this is a multipath member promote it to the real mpath
                if disk and disk.format.type == "multipath_member":
                    mpath_device = storage.devicetree.getChildren(disk)[0]
                    storage_log.info("kickstart: part: promoting %s to %s"
                                     % (disk.name, mpath_device.name))
                    disk = mpath_device
                if not disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % n)
                if not disk.partitionable:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Cannot install to read-only media %s." % n)

                should_clear = shouldClear(disk,
                                           storage.clearPartType,
                                           storage.clearPartDisks)
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

            cert = getEscrowCertificate(anaconda, self.escrowcert)
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

        anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Reboot(commands.reboot.FC6_Reboot):
    def execute(self, anaconda):
        anaconda.id.ksdata.skipSteps.append("complete")

class RaidData(commands.raid.F12_RaidData):
    def execute(self, anaconda):
        raidmems = []
        devicename = "md%d" % self.device

        storage = anaconda.id.storage
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint
            anaconda.id.ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            self.mountpoint = ""
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot" and anaconda.platform.supportsMdRaidBoot:
                type = anaconda.platform.defaultBootFSType
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
            anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return

        # Get a list of all the RAID members.
        for member in self.members:
            # if member is using --onpart, use original device
            member = anaconda.id.ksdata.onPart.get(member, member)
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
        kwargs["memberDevices"] = len(raidmems) - self.spares
        kwargs["totalDevices"] = len(raidmems)

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
            if devicename and devicename in [a.name for a in storage.mdarrays]:
                raise KickstartValueError(formatErrorMsg(self.lineno, msg="The Software RAID array name \"%s\" is already in use." % devicename))

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

            cert = getEscrowCertificate(anaconda, self.escrowcert)
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

        anaconda.id.ksdata.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class RootPw(commands.rootpw.F8_RootPw):
    def execute(self, anaconda):
        anaconda.id.rootPassword["password"] = self.password
        anaconda.id.rootPassword["isCrypted"] = self.isCrypted
        anaconda.id.rootPassword["lock"] = self.lock
        anaconda.id.ksdata.skipSteps.append("accounts")

class SELinux(commands.selinux.FC3_SELinux):
    def execute(self, anaconda):
        anaconda.id.security.setSELinux(self.selinux)

class SkipX(commands.skipx.FC3_SkipX):
    def execute(self, anaconda):
        anaconda.id.ksdata.skipSteps.extend(["setsanex", "videocard", "xcustom"])

        if anaconda.id.desktop is not None:
            anaconda.id.desktop.setDefaultRunLevel(3)

class Timezone(commands.timezone.FC6_Timezone):
    def execute(self, anaconda):
        # check validity
        tab = zonetab.ZoneTab()
        if self.timezone not in (entry.tz.replace(' ','_') for entry in
                                 tab.getEntries()):
            log.warning("Timezone %s set in kickstart is not valid." % (self.timezone,))

        anaconda.id.timezone.setTimezoneInfo(self.timezone, self.isUtc)
        anaconda.id.ksdata.skipSteps.append("timezone")

class Upgrade(commands.upgrade.F11_Upgrade):
    def execute(self, anaconda):
        anaconda.id.setUpgrade(self.upgrade)

class VolGroupData(commands.volgroup.FC3_VolGroupData):
    def execute(self, anaconda):
        pvs = []

        storage = anaconda.id.storage
        devicetree = storage.devicetree

        storage.doAutoPart = False

        # Get a list of all the physical volume devices that make up this VG.
        for pv in self.physvols:
            # if pv is using --onpart, use original device
            pv = anaconda.id.ksdata.onPart.get(pv, pv)
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
        elif self.vgname in [vg.name for vg in storage.vgs]:
            raise KickstartValueError(formatErrorMsg(self.lineno, msg="The volume group name \"%s\" is already in use." % self.vgname))
        else:
            request = storage.newVG(pvs=pvs,
                                    name=self.vgname,
                                    peSize=self.pesize/1024.0)

            storage.createDevice(request)

class XConfig(commands.xconfig.F10_XConfig):
    def execute(self, anaconda):
        if self.startX:
            anaconda.id.desktop.setDefaultRunLevel(5)

        if self.defaultdesktop:
            anaconda.id.desktop.setDefaultDesktop(self.defaultdesktop)

class ZeroMbr(commands.zerombr.FC3_ZeroMbr):
    def execute(self, anaconda):
        anaconda.id.storage.zeroMbr = 1

class ZFCP(commands.zfcp.F12_ZFCP):
    def parse(self, args):
        fcp = commands.zfcp.F12_ZFCP.parse(self, args)
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
        "firstboot": Firstboot,
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
        "zerombr": ZeroMbr,
        "zfcp": ZFCP,
}

dataMap = {
        "LogVolData": LogVolData,
        "NetworkData": NetworkData,
        "PartData": PartitionData,
        "RaidData": RaidData,
        "VolGroupData": VolGroupData,
}

superclass = returnClassForVersion(RHEL6)

class AnacondaKSHandler(superclass):
    def __init__ (self, anaconda):
        superclass.__init__(self, commandUpdates=commandMap, dataUpdates=dataMap)
        self.packages = AnacondaKSPackages()

        self.permanentSkipSteps = []
        self.skipOnTextInteractive = []
        self.skipSteps = []
        self.showSteps = []
        self.anaconda = anaconda
        self.id = self.anaconda.id
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

    def execute(self):
        try:
            for obj in filter(lambda o: hasattr(o, "execute"), self._dataObjs):
                obj.execute(self.anaconda)
        except KickstartError as e:
            if self.anaconda.intf:
                self.anaconda.intf.kickstartErrorWindow(e.__str__())
                self.anaconda.intf.shutdown()
                sys.exit(0)
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
    except IOError, e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % e.filename)
            sys.exit(1)
        else:
            print _("The following error was found while parsing the kickstart "
                    "configuration file:\n\n%s") % e
            sys.exit(1)
    except KickstartError, e:
       if anaconda.intf:
           anaconda.intf.kickstartErrorWindow(e.__str__())
           sys.exit(1)
       else:
            print _("The following error was found while parsing the kickstart "
                    "configuration file:\n\n%s") % e
            sys.exit(1)

    # run %pre scripts
    runPreScripts(anaconda, ksparser.handler.scripts)

def parseKickstart(anaconda, file):
    try:
        file = preprocessKickstart(file)
    except KickstartError, msg:
        stdoutLog.critical(_("Error processing %%ksappend lines: %s") % msg)
        sys.exit(1)
    except Exception, e:
        stdoutLog.critical(_("Unknown error processing %%ksappend lines: %s") % e)
        sys.exit(1)

    handler = AnacondaKSHandler(anaconda)
    ksparser = AnacondaKSParser(handler)

    # We need this so all the /dev/disk/* stuff is set up before parsing.
    udev_trigger(subsystem="block")
    # So that drives onlined by these can be used in the ks file
    storage.iscsi.iscsi().startup()
    storage.fcoe.fcoe().startup()
    storage.zfcp.ZFCP().startup()
    # Note we do NOT call dasd.startup() here, that does not online drives, but
    # only checks if they need formatting, which requires zerombr to be known
    detect_multipaths()

    try:
        ksparser.readKickstart(file)
    except IOError, e:
        # We may not have an intf now, but we can do better than just raising
        # the exception.
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % e.filename)
            sys.exit(1)
        else:
            print _("The following error was found while parsing the kickstart "
                    "configuration file:\n\n%s") % e
            sys.exit(1)
    except KickstartError, e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(e.__str__())
            sys.exit(1)
        else:
            print _("The following error was found while parsing the kickstart "
                    "configuration file:\n\n%s") % e
            sys.exit(1)

    return handler

def runPostScripts(anaconda):
    if not anaconda.id.ksdata:
        return

    postScripts = filter (lambda s: s.type == KS_SCRIPT_POST,
                          anaconda.id.ksdata.scripts)

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
    if anaconda.intf is not None:
        w = anaconda.intf.waitWindow(_("Pre-Installation"),
                            _("Running pre-installation scripts"))
    
    map (lambda s: s.run("/", flags.serial, anaconda.intf), preScripts)

    log.info("All kickstart %%pre script(s) have been run")
    if anaconda.intf is not None:
        w.pop()

def runTracebackScripts(anaconda):
    log.info("Running kickstart %%traceback script(s)")
    for script in filter (lambda s: s.type == KS_SCRIPT_TRACEBACK,
                          anaconda.id.ksdata.scripts):
        script.run("/", flags.serial)
    log.info("All kickstart %%traceback script(s) have been run")

def selectPackages(anaconda):
    ksdata = anaconda.id.ksdata
    ignoreAll = False

    # If no %packages header was seen, use the installclass's default group
    # selections.  This can also be explicitly specified with %packages
    # --default.  Otherwise, select whatever was given (even if it's nothing).
    if not ksdata.packages.seen or ksdata.packages.default:
        anaconda.id.instClass.setGroupSelection(anaconda)
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
    ksdata = anaconda.id.ksdata
    interactive = ksdata.interactive.interactive

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
        dispatch.skipStep("installtype")
    else:
        anaconda.id.instClass.setSteps(anaconda)
        dispatch.skipStep("findrootparts")

    if interactive or flags.autostep:
        dispatch.skipStep("installtype")
        dispatch.skipStep("bootdisk")

    dispatch.skipStep("bootdisk")
    dispatch.skipStep("betanag")
    dispatch.skipStep("installtype")
    dispatch.skipStep("network")

    # Storage is initialized for us right when kickstart processing starts.
    dispatch.skipStep("storageinit")

    if not interactive:
        # Don't show confirmation screens on non-interactive installs.
        dispatch.skipStep("confirminstall")
        dispatch.skipStep("confirmupgrade")
        dispatch.skipStep("welcome")

    if not interactive and not anaconda.id.storage.ignoreDiskInteractive:
        # Since ignoredisk is optional and not specifying it means you want to
        # consider all possible disks, we should not stop on the filter steps
        # unless it's an interactive install.
        dispatch.skipStep("filter")
        dispatch.skipStep("filtertype")

    # Make sure to automatically reboot even in interactive if told to.
    if interactive and ksdata.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
        dispatch.skipStep("complete")

    # If the package section included anything, skip group selection unless
    # they're in interactive.
    if ksdata.upgrade.upgrade:
        ksdata.skipSteps.extend(["tasksel", "group-selection"])

        # Special check for this, since it doesn't make any sense.
        if ksdata.packages.seen:
            warnings.warn("Ignoring contents of %packages section due to upgrade.")
    elif havePackages(ksdata.packages):
        if interactive and anaconda.id.displayMode == "t":
            ksdata.skipOnTextInteractive.extend(["tasksel", "group-selection"])
        elif interactive:
            ksdata.showSteps.extend(["tasksel", "group-selection"])
        else:
            ksdata.skipSteps.extend(["tasksel", "group-selection"])
    else:
        if ksdata.packages.seen:
            ksdata.skipSteps.extend(["tasksel", "group-selection"])
        else:
            ksdata.showSteps.extend(["tasksel", "group-selection"])

    if interactive:
        if anaconda.id.displayMode == "t":
            for n in ksdata.skipOnTextInteractive:
                dispatch.skipStep(n, permanent=1)
    else:
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
    if anaconda.id.displayMode == "t":
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
