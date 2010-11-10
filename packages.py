#
# packages.py: package management - mainly package installation
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import isys
import os
import timer
import time
import sys
import string
import language
import fsset
import kudzu
import shutil
import traceback
from flags import flags
from product import *
from constants import *
from installmethod import FileCopyException

import rhpl
from rhpl.translate import _
import rhpl.arch

import logging
log = logging.getLogger("anaconda")

def doPostAction(anaconda):
    anaconda.id.instClass.postAction(anaconda, flags.serial)

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
                       ("/tmp/ramfs/X.log", "anaconda.xlog")):
        if os.access(fn, os.R_OK):
            try:
                shutil.copyfile(fn, "%s/var/log/%s" %(anaconda.rootPath, dest))
                os.chmod("%s/var/log/%s" %(anaconda.rootPath, dest), 0600)
            except:
                pass

def writeXConfiguration(anaconda):
    testmode = flags.test

# comment out to test
    if testmode:
        return
# end code to comment to test 
# uncomment to test writing X config in test mode
#    try:
#	os.mkdir("/tmp/etc")
#    except:
#	pass
#    try:
#	os.mkdir("/tmp/etc/X11")
#    except:
#	pass
#    instPath = '/'
# end code for test writing

    if anaconda.id.xsetup.skipx:
        return

    card = anaconda.id.videocard.primaryCard()
    if not card:
	return

    log.info("Writing X configuration")
    if not testmode:
        fn = anaconda.rootPath
    else:
        fn = "/tmp/"

    anaconda.id.xsetup.write(fn+"/etc/X11", anaconda.id.mouse, anaconda.id.keyboard)
    anaconda.id.desktop.write(anaconda.rootPath)

def doMigrateFilesystems(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        return DISPATCH_NOOP

    if anaconda.id.fsset.haveMigratedFilesystems():
        return DISPATCH_NOOP

    anaconda.id.fsset.migrateFilesystems (anaconda.rootPath)

    if anaconda.id.upgrade:
        # if we're upgrading, we may need to do lvm device node hackery
        anaconda.id.fsset.makeLVMNodes(anaconda.rootPath, trylvm1 = 1)
        # and we should write out a new fstab with the migrated fstype
        anaconda.id.fsset.write(anaconda.rootPath)
    

def turnOnFilesystems(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        log.info("unmounting filesystems")
	anaconda.id.fsset.umountFilesystems(anaconda.rootPath)
	return

    if flags.setupFilesystems:
	if not anaconda.id.upgrade:
            anaconda.id.partitions.doMetaDeletes(anaconda.id.diskset)
            anaconda.id.fsset.setActive(anaconda.id.diskset)
            if not anaconda.id.fsset.isActive():
                anaconda.id.diskset.savePartitions ()
            anaconda.id.partitions.doEncryptionRetrofits()
            anaconda.id.fsset.checkBadblocks(anaconda.rootPath)
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
	    anaconda.id.fsset.makeFilesystems (anaconda.rootPath)
            anaconda.id.fsset.mountFilesystems (anaconda)

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

    if rhpl.getArch() == "s390":
        return
    args = [ "--hctosys" ]
    if anaconda.id.timezone.utc:
        args.append("-u")
    elif anaconda.id.timezone.arc:
        args.append("-a")

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
                 "/var/log/wtmp", "/var/run/utmp",
                 "/dev/log", "/var/lib/rpm", "/", "/etc/raidtab",
                 "/etc/mdadm.conf", "/etc/hosts", "/etc/sysconfig/network",
                 "/root/install.log", "/root/install.log.syslog",
                 "/etc/shadow", "/etc/shadow-", "/etc/gshadow",
                 "/var/log/lastlog", "/var/log/btmp",
                 "/var/lib/multipath", "/var/lib/multipath/bindings",
                 "/etc/multipath.conf", "/etc/sysconfig/keyboard"]

        vgs = []
        for entry in anaconda.id.partitions.requests:
            if isinstance(entry, partRequests.VolumeGroupRequestSpec):
                vgs.append("/dev/%s" %(entry.volumeGroupName,))

        # ugh, this is ugly
        for dir in ["/etc/sysconfig/network-scripts", "/var/lib/rpm", "/etc/lvm", "/dev/mapper", "/etc/iscsi", "/var/lib/iscsi"] + vgs:

            def findfiles(path):
                if not os.path.isdir(anaconda.rootPath + path):
                    files.append(path)
                    return
                dirfiles = os.listdir(anaconda.rootPath + path)
                for file in dirfiles:
                    findfiles(path + '/' + file)
                files.append(path)

            findfiles(dir)

        for f in files:
            if not os.access("%s/%s" %(anaconda.rootPath, f), os.R_OK):
                log.warning("%s doesn't exist" %(f,))
                continue
            ret = isys.resetFileContext(os.path.normpath(f),
                                        anaconda.rootPath)
            log.info("set fc of %s to %s" %(f, ret))

    return

#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log.info("recreating initrd for %s" % (kernelTag,))
    iutil.execWithRedirect("/sbin/new-kernel-pkg",
                           [ "--mkinitrd", "--depmod", "--install", kernelTag ],
                           stdout = None, stderr = None,
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
    if key and not anaconda.id.instClass.skipkey and anaconda.isKickstart and \
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
                    "Fedora Core": "Fedora Core" }

    
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
	    rc = anaconda.intf.messageWindow( _("Rebooting System"),
                                     msg,
                                     type="custom", custom_icon="warning",
                                     custom_buttons=buttons)
	    if rc:
		sys.exit(0)
	else:
	    break

# FIXME: this is a kind of poor way to do this, but it will work for now
def selectPackageConditionals(grpset, grp):
    xmlgrp = grpset.compsxml.groups[grp.basename]

    for package in xmlgrp.pkgConditionals.keys():
        req = xmlgrp.pkgConditionals[package]
        if not grpset.hdrlist.has_key(package):
            log.warning ("Missing %s which is in a conditional" %(package,))
            continue
        # add to the deps in the dependencies structure for the
        # package.  this should take care of whenever we're
        # selected
        grpset.hdrlist[req].addDeps([package], main = 0)
        if grpset.hdrlist[req].isSelected():
            grpset.hdrlist[package].select()
            grpset.hdrlist[package].usecount += grpset.hdrlist[req].usecount - 1
            grp.selectDeps([package], uses = grpset.hdrlist[req].usecount)

# Loop over all the selected groups and make sure all the conditionals are
# met.
def fixupConditionals(grpset):
    for grp in grpset.groups:
        if grpset.groups[grp].isSelected():
            selectPackageConditionals(grpset, grpset.groups[grp])

def selectLanguageSupportGroups(grpset, instLanguage):
    if not grpset.groups.has_key("language-support"):
        return

    langs = []
    for l in language.expandLangs (instLanguage.getDefault()):
        langs.append(l)

    grp = grpset.groups["language-support"]
    for (pid, pdict) in grp.packages.items():
        if pdict['meta'] != 1:
            continue
        if not grpset.groups.has_key(pid):
            continue
        group = grpset.groups[pid]

        if group.langonly is not None and group.langonly in langs:
            grp.selectPackage(pid)
            grp.usecount = grp.usecount + 1
            selectPackageConditionals(grpset, group)

    if grp.usecount > 0:
        grpset.groups["language-support"].select()

def doReIPL(anaconda):
    if not rhpl.getArch() in ['s390', 's390x']:
        return DISPATCH_NOOP

    messageInfo = iutil.reIPL(anaconda, os.getppid())

    # @TBD seeing a bug here where anaconda.canReIPL and anaconda.reIPLMessage are
    # not initialized even though they were in Anaconda.__init__()
    if messageInfo is None:
        anaconda.canReIPL = True

        anaconda.reIPLMessage = None
    else:
        anaconda.canReIPL = False

        (errorMessage, rebootInstr) = messageInfo

        # errorMessage intentionally not shown in UI
        anaconda.reIPLMessage = rebootInstr

    return DISPATCH_FORWARD
