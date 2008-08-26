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
import fsset
import lvm
import shutil
import traceback
from flags import flags
from product import *
from constants import *

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
                       ("/tmp/X.log", "anaconda.xlog")):
        if os.access(fn, os.R_OK):
            try:
                shutil.copyfile(fn, "%s/var/log/%s" %(anaconda.rootPath, dest))
                os.chmod("%s/var/log/%s" %(anaconda.rootPath, dest), 0600)
            except:
                pass

def doMigrateFilesystems(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        return DISPATCH_NOOP

    if anaconda.id.fsset.haveMigratedFilesystems():
        return DISPATCH_NOOP

    anaconda.id.fsset.migrateFilesystems (anaconda)

    if anaconda.id.upgrade:
        # if we're upgrading, we may need to do lvm device node hackery
        anaconda.id.fsset.makeLVMNodes(anaconda.rootPath, trylvm1 = 1)
        # and we should write out a new fstab with the migrated fstype
        anaconda.id.fsset.write(anaconda.rootPath)
    

def turnOnFilesystems(anaconda):
    def handleResizeError(e, dev):
        if os.path.exists("/tmp/resize.out"):
            details = open("/tmp/resize.out", "r").read()
        else:
            details = "%s" %(e,)
        anaconda.intf.detailedMessageWindow(_("Resizing Failed"),
                                            _("There was an error encountered "
                                            "resizing the device %s.") %(dev,),
                                            details,
                                            type = "custom",
                                            custom_buttons = [_("_Exit installer")])
        sys.exit(1)

    if anaconda.dir == DISPATCH_BACK:
        log.info("unmounting filesystems")
	anaconda.id.fsset.umountFilesystems(anaconda.rootPath)
	return

    if flags.setupFilesystems:
	if not anaconda.id.upgrade:
            if not anaconda.id.fsset.isActive():
                # turn off any swaps that we didn't turn on
                # needed for live installs
                iutil.execWithRedirect("swapoff", ["-a"],
                                       stdout = "/dev/tty5", stderr="/dev/tty5",
                                       searchPath = 1)
            anaconda.id.partitions.doMetaDeletes(anaconda.id.diskset)
            anaconda.id.fsset.setActive(anaconda.id.diskset)
            try:
                anaconda.id.fsset.shrinkFilesystems(anaconda.id.diskset, anaconda.rootPath)
            except fsset.ResizeError, (e, dev):
                handleResizeError(e, dev)

            if not anaconda.id.fsset.isActive():
                anaconda.id.diskset.savePartitions ()
                # this is somewhat lame, but we seem to be racing with
                # device node creation sometimes.  so wait for device nodes
                # to settle
                time.sleep(1)
                w = anaconda.intf.waitWindow(_("Activating"), _("Activating new partitions.  Please wait..."))
                rc = iutil.execWithRedirect("udevsettle", [],
                                            stdout = "/dev/tty5",
                                            stderr = "/dev/tty5",
                                            searchPath = 1)
                w.pop()

                try:
                    anaconda.id.partitions.doMetaResizes(anaconda.id.diskset)
                except lvm.LVResizeError, e:
                    handleResizeError("%s" %(e,), "%s/%s" %(e.vgname, e.lvname))
            try:
                anaconda.id.fsset.growFilesystems(anaconda.id.diskset, anaconda.rootPath)
            except fsset.ResizeError, (e, dev):
                handleResizeError(e, dev)

            if not anaconda.id.fsset.volumesCreated:
                try:
                    anaconda.id.fsset.createLogicalVolumes(anaconda.rootPath)
                except SystemError, e:
                    log.error("createLogicalVolumes failed with %s", str(e))
                    anaconda.intf.messageWindow(_("LVM operation failed"),
                                        str(e)+"\n\n"+_("The installer will now exit..."),
                                        type="custom", custom_icon="error", custom_buttons=[_("_Reboot")])
	            sys.exit(0)

            anaconda.id.fsset.formatSwap(anaconda.rootPath)
            anaconda.id.fsset.turnOnSwap(anaconda.rootPath)
            anaconda.id.fsset.makeFilesystems(anaconda.rootPath,
                                              anaconda.backend.skipFormatRoot)
            anaconda.id.fsset.mountFilesystems(anaconda,0,0,
                                               anaconda.backend.skipFormatRoot)

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
        except OSError, (errno, msg):
            log.error("Error copying timezone (from %s): %s" %(tzfile, msg))

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
    import partRequests

    if flags.selinux:
        log.info("setting SELinux contexts for anaconda created files")

        files = ["/etc/rpm/platform", "/etc/rpm/macros",
                 "/etc/lilo.conf.anaconda", "/lib64", "/usr/lib64",
                 "/etc/blkid.tab", "/etc/blkid.tab.old", 
                 "/etc/mtab", "/etc/fstab", "/etc/resolv.conf",
                 "/etc/modprobe.conf", "/etc/modprobe.conf~",
                 "/var/log/wtmp", "/var/run/utmp", "/etc/crypttab",
                 "/dev/log", "/var/lib/rpm", "/", "/etc/raidtab",
                 "/etc/mdadm.conf", "/etc/hosts", "/etc/sysconfig/network",
                 "/lib/udev/rules.d/70-persistent-net.rules",
                 "/root/install.log", "/root/install.log.syslog",
                 "/etc/shadow", "/etc/shadow-", "/etc/gshadow"]

        vgs = []
        for entry in anaconda.id.partitions.requests:
            if isinstance(entry, partRequests.VolumeGroupRequestSpec):
                vgs.append("/dev/%s" %(entry.volumeGroupName,))

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

    # FIXME: and make sure that the rpmdb doesn't have stale locks :/
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % rootPath):
        try:
            os.unlink(rpmfile)
        except:
            log.debug("failed to unlink %s" % rpmfile)

    ts = rpm.TransactionSet(rootPath)

    mi = ts.dbMatch('provides', 'kernel')
    for h in mi:
        v = get_version(h)
        tag = get_tag(h)
        if v == "" or tag == "":
            log.warning("Unable to determine kernel type/version for %s-%s-%s.%s" %(h['name'], h['version'], h['release'], h['arch'])) 
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
