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
from flags import flags
from product import *
from constants import *
from syslogd import syslog
from installmethod import FileCopyException

import rhpl
from rhpl.translate import _
import rhpl.arch

import logging
log = logging.getLogger("anaconda")

def doPostAction(id, instPath, intf = None):
    id.instClass.postAction(instPath, flags.serial, intf)

def firstbootConfiguration(id, instPath):
    if id.firstboot == FIRSTBOOT_RECONFIG:
        f = open(instPath + '/etc/reconfigSys', 'w+')
        f.close()
    elif id.firstboot == FIRSTBOOT_SKIP:
        f = open(instPath + '/etc/sysconfig/firstboot', 'w+')
        f.write('RUN_FIRSTBOOT=NO')
        f.close()

    return
        

def writeKSConfiguration(id, instPath):
    log.info("Writing autokickstart file")
    if not flags.test:
	fn = instPath + "/root/anaconda-ks.cfg"
    else:
	fn = "/tmp/anaconda-ks.cfg"

    id.writeKS(fn)

def copyAnacondaLogs(instPath):
    log.info("Copying anaconda logs")
    for (fn, dest) in (("/tmp/anaconda.log", "anaconda.log"),
                       ("/tmp/syslog", "anaconda.syslog"),
                       ("/tmp/ramfs/X.log", "anaconda.xlog")):
        if os.access(fn, os.R_OK):
            try:
                shutil.copyfile(fn, "%s/var/log/%s" %(instPath, dest))
                os.chmod("%s/var/log/%s" %(instPath, dest), 0600)
            except:
                pass

def writeXConfiguration(id, instPath):
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

    if id.xsetup.skipx:
        return

    card = id.videocard.primaryCard()
    if not card:
	return

    log.info("Writing X configuration")
    if not testmode:
        fn = instPath
    else:
        fn = "/tmp/"

    id.xsetup.write(fn+"/etc/X11", id.mouse, id.keyboard)
    id.desktop.write(instPath)

def doMigrateFilesystems(dir, thefsset, diskset, upgrade, instPath):
    if dir == DISPATCH_BACK:
        return DISPATCH_NOOP

    if thefsset.haveMigratedFilesystems():
        return DISPATCH_NOOP

    thefsset.migrateFilesystems (instPath)

    # if we're upgrading, we may need to do lvm device node hackery
    if upgrade:
        thefsset.makeLVMNodes(instPath, trylvm1 = 1)
    

def turnOnFilesystems(dir, thefsset, diskset, partitions, upgrade, instPath):
    if dir == DISPATCH_BACK:
        log.info("unmounting filesystems")
	thefsset.umountFilesystems(instPath)
	return

    if flags.setupFilesystems:
	if not upgrade:
            partitions.doMetaDeletes(diskset)
            thefsset.setActive(diskset)
            if not thefsset.isActive():
                diskset.savePartitions ()
            thefsset.checkBadblocks(instPath)
            if not thefsset.volumesCreated:
                thefsset.createLogicalVolumes(instPath)
            thefsset.formatSwap(instPath)
            thefsset.turnOnSwap(instPath)
	    thefsset.makeFilesystems (instPath)
            thefsset.mountFilesystems (instPath)

def setupTimezone(timezone, upgrade, instPath, dir):
    # we don't need this on an upgrade or going backwards
    if upgrade or (dir == DISPATCH_BACK):
        return

    # dont do this in test mode!
    if flags.test or flags.rootpath:
	return
    
    os.environ["TZ"] = timezone.tz
    tzfile = "/usr/share/zoneinfo/" + timezone.tz
    if not os.access(tzfile, os.R_OK):
        log.error("unable to set timezone")
    else:
        try:
            shutil.copyfile(tzfile, "/etc/localtime")
        except OSError, (errno, msg):
            log.error("Error copying timezone (from %s): %s" %(tzfile, msg))

    if rhpl.getArch() == "s390":
        return
    args = [ "/usr/sbin/hwclock", "--hctosys" ]
    if timezone.utc:
        args.append("-u")
    elif timezone.arc:
        args.append("-a")

    try:
        iutil.execWithRedirect(args[0], args, stdin = None,
                               stdout = "/dev/tty5", stderr = "/dev/tty5")
    except RuntimeError:
        log.error("Failed to set clock")


# FIXME: this is a huge gross hack.  hard coded list of files
# created by anaconda so that we can not be killed by selinux
def setFileCons(instPath, partitions):
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
                 "/etc/mdadm.conf"]

        vgs = []
        for entry in partitions.requests:
            if isinstance(entry, partRequests.VolumeGroupRequestSpec):
                vgs.append("/dev/%s" %(entry.volumeGroupName,))

        # ugh, this is ugly
        for dir in ["/var/lib/rpm", "/etc/lvm", "/dev/mapper"] + vgs:
            def addpath(x): return dir + "/" + x

            if not os.path.isdir(instPath + dir):
                continue
            dirfiles = os.listdir(instPath + dir)
            files.extend(map(addpath, dirfiles))
            files.append(dir)

        # blah, to work in a chroot, we need to actually be inside so the
        # regexes will work
        child = os.fork()
        if (not child):
            os.chroot(instPath)
            for f in files:
                if not os.access("%s" %(f,), os.R_OK):
                    log.warning("%s doesn't exist" %(f,))
                    continue
                ret = isys.resetFileContext(f)
                log.info("set fc of %s to %s" %(f, ret))
            os._exit(0)

        try:
            os.waitpid(child, 0)
        except OSError, (num, msg):
            pass
            

    return

# XXX: large hack lies here
def migrateMouseConfig(instPath, instLog):
    if not os.access (instPath + "/usr/sbin/fix-mouse-psaux", os.X_OK):
        return

    argv = [ "/usr/sbin/fix-mouse-psaux" ]

    logfile = os.open (instLog, os.O_APPEND)
    iutil.execWithRedirect(argv[0], argv, root = instPath,
			   stdout = logfile, stderr = logfile)
    os.close(logfile)


def migrateXinetd(instPath, instLog):
    if not os.access (instPath + "/usr/sbin/inetdconvert", os.X_OK):
	return

    if not os.access (instPath + "/etc/inetd.conf.rpmsave", os.R_OK):
	return

    argv = [ "/usr/sbin/inetdconvert", "--convertremaining",
	     "--inetdfile", "/etc/inetd.conf.rpmsave" ]

    logfile = os.open (instLog, os.O_APPEND)
    iutil.execWithRedirect(argv[0], argv, root = instPath,
			   stdout = logfile, stderr = logfile)
    os.close(logfile)

def copyExtraModules(instPath, grpset, extraModules):
    kernelVersions = grpset.kernelVersionList()
    foundModule = 0

    try:
        f = open("/etc/arch")
        arch = f.readline().strip()
        del f
    except IOError:
        arch = os.uname()[2]

    for (path, name) in extraModules:
        if not path:
            path = "/modules.cgz"
	pattern = ""
	names = ""
	for (n, tag) in kernelVersions:
            if tag == "up":
                pkg = "kernel"
            else:
                pkg = "kernel-%s" %(tag,)
            arch = grpset.hdrlist[pkg]['arch']
            # version 1 path
            pattern = pattern + " %s/%s/%s.ko " % (n, arch, name)
            # version 0 path
            pattern = pattern + " %s/%s.ko " % (n, name)
            names = names + " %s.ko" % (name,)
	command = ("cd %s/lib/modules; gunzip < %s | "
                   "%s/bin/cpio --quiet -iumd %s" % 
                   (instPath, path, instPath, pattern))
	log.info("running: '%s'" % (command, ))
	os.system(command)

	for (n, tag) in kernelVersions:
            if tag == "up":
                pkg = "kernel"
            else:
                pkg = "kernel-%s" %(tag,)
            
	    toDir = "%s/lib/modules/%s/updates" % \
		    (instPath, n)
	    to = "%s/%s.ko" % (toDir, name)

            if (os.path.isdir("%s/lib/modules/%s" %(instPath, n)) and not
                os.path.isdir("%s/lib/modules/%s/updates" %(instPath, n))):
                os.mkdir("%s/lib/modules/%s/updates" %(instPath, n))
            if not os.path.isdir(toDir):
                continue

            arch = grpset.hdrlist[pkg]['arch']
            for p in ("%s/%s.ko" %(arch, name), "%s.ko" %(name,)):
                fromFile = "%s/lib/modules/%s/%s" % (instPath, n, p)

                if (os.access(fromFile, os.R_OK)):
                    log.info("moving %s to %s" % (fromFile, to))
                    os.rename(fromFile, to)
                    # the file might not have been owned by root in the cgz
                    os.chown(to, 0, 0)
                    foundModule = 1
                else:
                    log.warning("missing DD module %s (this may be okay)" % 
                        fromFile)

    if foundModule == 1:
        for (n, tag) in kernelVersions:
            recreateInitrd(n, instPath)


#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log.info("recreating initrd for %s" % (kernelTag,))
    iutil.execWithRedirect("/sbin/new-kernel-pkg",
                           [ "/sbin/new-kernel-pkg", "--mkinitrd",
                             "--depmod", "--install", kernelTag ],
                           stdout = None, stderr = None,
                           searchPath = 1, root = instRoot)

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
