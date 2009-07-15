#
# packages.py: package management - mainly package installation
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#            Matt Wilson <msw@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

import glob
import iutil
import isys
import os
import time
import sys
import string
import language
import shutil
import traceback
from flags import flags
from product import *
from constants import *
from upgrade import bindMountDevDirectory
from storage.errors import *

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def doPostAction(anaconda):
    anaconda.id.instClass.postAction(anaconda)

def firstbootConfiguration(anaconda):
    if anaconda.id.firstboot == FIRSTBOOT_RECONFIG:
        f = open(anaconda.rootPath + '/etc/reconfigSys', 'w+')
        f.close()
    elif anaconda.id.firstboot == FIRSTBOOT_SKIP:
        f = open(anaconda.rootPath + '/etc/sysconfig/firstboot', 'w+')
        f.write('RUN_FIRSTBOOT=NO')
        f.close()

    return
        
def writeRegKey(anaconda):
    if anaconda.id.instClass.installkey and os.path.exists(anaconda.rootPath + "/etc/sysconfig/rhn"):
        f = open(anaconda.rootPath + "/etc/sysconfig/rhn/install-num", "w+")
        f.write("%s\n" %(anaconda.id.instClass.installkey,))
        f.close()
        os.chmod(anaconda.rootPath + "/etc/sysconfig/rhn/install-num", 0600)

def writeKSConfiguration(anaconda):
    log.info("Writing autokickstart file")
    if not flags.test:
	fn = anaconda.rootPath + "/root/anaconda-ks.cfg"
    else:
	fn = "/tmp/anaconda-ks.cfg"

    anaconda.id.writeKS(fn)

def copyAnacondaLogs(anaconda):
    log.info("Copying anaconda logs")
    for (fn, dest) in (("/tmp/anaconda.log", "anaconda.log"),
                       ("/tmp/syslog", "anaconda.syslog"),
                       ("/tmp/X.log", "anaconda.xlog"),
                       ("/tmp/program.log", "program.log"),
                       ("/tmp/storage.log", "storage.log"),
                       ("/tmp/yum.log", "yum.log")):
        if os.access(fn, os.R_OK):
            try:
                shutil.copyfile(fn, "%s/var/log/%s" %(anaconda.rootPath, dest))
                os.chmod("%s/var/log/%s" %(anaconda.rootPath, dest), 0600)
            except:
                pass

def turnOnFilesystems(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        if not anaconda.id.upgrade:
            log.info("unmounting filesystems")
            anaconda.id.storage.fsset.umountFilesystems(anaconda.rootPath)
        return DISPATCH_NOOP

    if flags.setupFilesystems:
	if not anaconda.id.upgrade:
            if not anaconda.id.storage.fsset.active:
                # turn off any swaps that we didn't turn on
                # needed for live installs
                iutil.execWithRedirect("swapoff", ["-a"],
                                       stdout = "/dev/tty5", stderr="/dev/tty5",
                                       searchPath = 1)
            anaconda.id.storage.devicetree.teardownAll()

        upgrade_migrate = False
        if anaconda.id.upgrade:
            for d in anaconda.id.storage.fsset.migratableDevices:
                if d.format.migrate:
                    upgrade_migrate = True

        try:
            anaconda.id.storage.doIt()
        except DeviceResizeError as (msg, device):
            # XXX does this make any sense? do we support resize of
            #     devices other than partitions?
            anaconda.intf.detailedMessageWindow(_("Device Resize Failed"),
                                _("An error was encountered while "
                                  "resizing device %s.") % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except DeviceCreateError as (msg, device):
            anaconda.intf.detailedMessageWindow(_("Device Creation Failed"),
                                _("An error was encountered while "
                                  "creating device %s.") % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except DeviceDestroyError as (msg, device):
            anaconda.intf.detailedMessageWindow(_("Device Removal Failed"),
                                _("An error was encountered while "
                                  "removing device %s.") % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except DeviceError as (msg, device):
            anaconda.intf.detailedMessageWindow(_("Device Setup Failed"),
                                _("An error was encountered while "
                                  "setting up device %s.") % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except FSResizeError as (msg, device):
            if os.path.exists("/tmp/resize.out"):
                details = open("/tmp/resize.out", "r").read()
            else:
                details = "%s" %(msg,)
            anaconda.intf.detailedMessageWindow(_("Resizing Failed"),
                                _("There was an error encountered while "
                                "resizing the device %s.") %(device,),
                                details,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except FSMigrateError as (msg, device):
            anaconda.intf.detailedMessageWindow(_("Migration Failed"),
                                _("An error was encountered while "
                                  "migrating filesystem on device %s.")
                                % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except FormatCreateError as (msg, device):
            anaconda.intf.detailedMessageWindow(_("Formatting Failed"),
                                _("An error was encountered while "
                                  "formatting device %s.") % (device,),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_Exit installer")])
            sys.exit(1)
        except Exception as msg:
            # catch-all
            rc = anaconda.intf.detailedMessageWindow(_("Storage Activation Failed"),
                                _("An error was encountered while "
                                  "activating your storage configuration."),
                                msg,
                                type = "custom",
                                custom_buttons = [_("_File Bug"), _("_Exit installer")])

            if rc == 0:
                raise
            elif rc == 1:
                sys.exit(1)

        if not anaconda.id.upgrade:
            anaconda.id.storage.fsset.turnOnSwap(anaconda)
            anaconda.id.storage.fsset.mountFilesystems(anaconda,
                                                       raiseErrors=False,
                                                       readOnly=False,
                                                       skipRoot=anaconda.backend.skipFormatRoot)
        else:
            if upgrade_migrate:
                # we should write out a new fstab with the migrated fstype
                shutil.copyfile("%s/etc/fstab" % anaconda.rootPath,
                                "%s/etc/fstab.anaconda" % anaconda.rootPath)
                anaconda.id.storage.fsset.write(anaconda.rootPath)

            # and make sure /dev is mounted so we can read the bootloader
            bindMountDevDirectory(anaconda.rootPath)


def setupTimezone(anaconda):
    # we don't need this on an upgrade or going backwards
    if anaconda.id.upgrade or anaconda.dir == DISPATCH_BACK:
        return

    # dont do this in test mode!
    if flags.test or flags.rootpath:
	return
    
    os.environ["TZ"] = anaconda.id.timezone.tz
    tzfile = "/usr/share/zoneinfo/" + anaconda.id.timezone.tz
    if not os.access(tzfile, os.R_OK):
        log.error("unable to set timezone")
    else:
        try:
            shutil.copyfile(tzfile, "/etc/localtime")
        except OSError as e:
            log.error("Error copying timezone (from %s): %s" %(tzfile, e.strerror))

    if iutil.isS390():
        return
    args = [ "--hctosys" ]
    if anaconda.id.timezone.utc:
        args.append("-u")

    try:
        iutil.execWithRedirect("/usr/sbin/hwclock", args, stdin = None,
                               stdout = "/dev/tty5", stderr = "/dev/tty5")
    except RuntimeError:
        log.error("Failed to set clock")


# FIXME: this is a huge gross hack.  hard coded list of files
# created by anaconda so that we can not be killed by selinux
def setFileCons(anaconda):
    if flags.selinux:
        log.info("setting SELinux contexts for anaconda created files")

        files = ["/etc/rpm/macros",
                 "/etc/lilo.conf.anaconda", "/lib64", "/usr/lib64",
                 "/etc/blkid.tab", "/etc/blkid.tab.old", 
                 "/etc/mtab", "/etc/fstab", "/etc/resolv.conf",
                 "/etc/modprobe.conf", "/etc/modprobe.conf~",
                 "/var/log/wtmp", "/var/run/utmp", "/etc/crypttab",
                 "/dev/log", "/var/lib/rpm", "/", "/etc/raidtab",
                 "/etc/mdadm.conf", "/etc/sysconfig/network",
                 "/etc/udev/rules.d/70-persistent-net.rules",
                 "/root/install.log", "/root/install.log.syslog",
                 "/etc/shadow", "/etc/shadow-", "/etc/gshadow"] + \
                glob.glob('/etc/dhclient-*.conf')

        vgs = ["/dev/%s" % vg.name for vg in anaconda.id.storage.vgs]

        # ugh, this is ugly
        for dir in ["/etc/sysconfig/network-scripts", "/var/lib/rpm", "/etc/lvm", "/dev/mapper", "/etc/iscsi", "/var/lib/iscsi", "/root", "/var/log", "/etc/modprobe.d", "/etc/sysconfig" ] + vgs:
            def addpath(x): return dir + "/" + x

            if not os.path.isdir(anaconda.rootPath + dir):
                continue
            dirfiles = os.listdir(anaconda.rootPath + dir)
            files.extend(map(addpath, dirfiles))
            files.append(dir)

        for f in files:
            if not os.access("%s/%s" %(anaconda.rootPath, f), os.R_OK):
                log.warning("%s doesn't exist" %(f,))
                continue
            ret = isys.resetFileContext(os.path.normpath(f),
                                        anaconda.rootPath)
            log.info("set fc of %s to %s" %(f, ret))

    return

# FIXME: using rpm directly here is kind of lame, but in the yum backend
# we don't want to use the metadata as the info we need would require
# the filelists.  and since we only ever call this after an install is
# done, we can be guaranteed this will work.  put here because it's also
# used for livecd installs
def rpmKernelVersionList(rootPath = "/"):
    import rpm

    def get_version(header):
        for f in header['filenames']:
            if f.startswith('/boot/vmlinuz-'):
                return f[14:]
            elif f.startswith('/boot/efi/EFI/redhat/vmlinuz-'):
                return f[29:]
        return ""

    def get_tag(header):
        if header['name'] == "kernel":
            return "base"
        elif header['name'].startswith("kernel-"):
            return header['name'][7:]
        return ""

    versions = []

    iutil.resetRpmDb(rootPath)
    ts = rpm.TransactionSet(rootPath)

    mi = ts.dbMatch('provides', 'kernel')
    for h in mi:
        v = get_version(h)
        tag = get_tag(h)
        if v == "" or tag == "":
            log.warning("Unable to determine kernel type/version for %s-%s-%s.%s" %(h['name'], h['version'], h['release'], h['arch'])) 
            continue
        # rpm really shouldn't return the same kernel more than once... but
        # sometimes it does (#467822)
        if (v, h['arch'], tag) in versions:
            continue
        versions.append( (v, h['arch'], tag) )

    return versions

#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log.info("recreating initrd for %s" % (kernelTag,))
    iutil.execWithRedirect("/sbin/new-kernel-pkg",
                           [ "--mkinitrd", "--depmod", "--install", kernelTag ],
                           stdout = "/dev/null", stderr = "/dev/null",
                           searchPath = 1, root = instRoot)

def regKeyScreen(anaconda):
    def checkRegKey(anaconda, key, quiet=0):
        rc = True
        try:
            anaconda.id.instClass.handleRegKey(key, anaconda.intf,
                                               not anaconda.isKickstart)
        except Exception, e:
            if not quiet:
                log.info("exception handling installation key: %s" %(e,))

                (type, value, tb) = sys.exc_info()
                list = traceback.format_exception(type, value, tb)
                for l in list:
                    log.debug(l)
                anaconda.intf.messageWindow(_("Invalid Key"),
                                        _("The key you entered is invalid."),
                                        type="warning")
            rc = False

        return rc
 
    key = anaconda.id.instClass.installkey or ""

    # handle existing key if we're headed forward
    if key and not anaconda.id.instClass.skipkey and \
       anaconda.dir == DISPATCH_FORWARD and checkRegKey(anaconda, key):
        return DISPATCH_FORWARD

    # if we're backing up we should allow them to reconsider skipping the key
    if anaconda.dir == DISPATCH_BACK and anaconda.id.instClass.skipkey:
        anaconda.id.instClass.skipkey = False

    while not anaconda.id.instClass.skipkey:
        rc = anaconda.intf.getInstallKey(anaconda, key)
        if rc is None and anaconda.dispatch.canGoBack():
            return DISPATCH_BACK
        elif rc is None:
            continue
        elif rc == SKIP_KEY:
            if anaconda.id.instClass.skipkeytext:
                rc = anaconda.intf.messageWindow(_("Skip"),
                                     _(anaconda.id.instClass.skipkeytext),
                                     type="custom", custom_icon="question",
                                     custom_buttons=[_("_Back"), _("_Skip")])
                if not rc:
                    continue
                # unset the key and associated data
                checkRegKey(anaconda, None, quiet=1)
                anaconda.id.instClass.skipkey = True
            break

        key = rc
        if checkRegKey(anaconda, key):
            break

    return DISPATCH_FORWARD

def betaNagScreen(anaconda):
    publicBetas = { "Red Hat Linux": "Red Hat Linux Public Beta",
                    "Red Hat Enterprise Linux": "Red Hat Enterprise Linux Public Beta",
                    "Fedora Core": "Fedora Core",
                    "Fedora": "Fedora" }

    
    if anaconda.dir == DISPATCH_BACK:
	return DISPATCH_NOOP

    fileagainst = None
    for (key, val) in publicBetas.items():
        if productName.startswith(key):
            fileagainst = val
    if fileagainst is None:
        fileagainst = "%s Beta" %(productName,)
    
    while 1:
	rc = anaconda.intf.messageWindow( _("Warning! This is pre-release software!"),
				 _("Thank you for downloading this "
				   "pre-release of %s.\n\n"
				   "This is not a final "
				   "release and is not intended for use "
				   "on production systems.  The purpose of "
				   "this release is to collect feedback "
				   "from testers, and it is not suitable "
				   "for day to day usage.\n\n"
				   "To report feedback, please visit:\n\n"
				   "   %s\n\n"
				   "and file a report against '%s'.\n")
                                   %(productName, bugzillaUrl, fileagainst),
				   type="custom", custom_icon="warning",
				   custom_buttons=[_("_Exit"), _("_Install anyway")])

	if not rc:
            if flags.rootpath:
                msg =  _("The installer will now exit...")
                buttons = [_("_Back"), _("_Exit")]
            else:
                msg =  _("Your system will now be rebooted...")
                buttons = [_("_Back"), _("_Reboot")]
	    rc = anaconda.intf.messageWindow( _("Warning! This is pre-release software!"),
                                     msg,
                                     type="custom", custom_icon="warning",
                                     custom_buttons=buttons)
	    if rc:
		sys.exit(0)
	else:
	    break

def doReIPL(anaconda):
#   # This is here as an example to fix the screen during the TUI debugging path
#   anaconda.intf.screen.suspend ()
#   import pdb
#   pdb.set_trace ()

    if not iutil.isS390():
        return DISPATCH_NOOP

    messageInfo = iutil.reIPL(anaconda, os.getppid())

    if messageInfo is None:
        anaconda.canReIPL = True
    else:
        anaconda.canReIPL = False

        (errorMessage, rebootInstr) = messageInfo

        # errorMessage intentionally not shown in UI
        anaconda.reIPLMessage = rebootInstr

    return DISPATCH_FORWARD
