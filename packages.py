#
# packages.py: package management - mainly package installation
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2003 Red Hat, Inc.
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
import rpm
import os
import timer
import time
import sys
import string
import pcmcia
import language
import fsset
import kudzu
from flags import flags
from product import *
from constants import *
from syslogd import syslog
from hdrlist import PKGTYPE_MANDATORY, PKGTYPE_DEFAULT
from installmethod import FileCopyException

from rhpl.translate import _
import rhpl.arch

import logging
log = logging.getLogger("anaconda")

def queryUpgradeContinue(intf, dir):
    if dir == DISPATCH_FORWARD:
        return

    rc = intf.messageWindow(_("Proceed with upgrade?"),
                       _("The file systems of the Linux installation "
                         "you have chosen to upgrade have already been "
                         "mounted. You cannot go back past this point. "
                         "\n\n") + 
                     _( "Would you like to continue with the upgrade?"),
                                      type = "yesno")
    if rc == 0:
        sys.exit(0)
    return DISPATCH_FORWARD

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
        

def writeConfiguration(id, instPath):
    log.info("Writing main configuration")
    if not flags.test:
        id.write(instPath)

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
                iutil.copyFile(fn, "%s/var/log/%s" %(instPath, dest))
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

        if os.access (instPath + "/etc/X11/X", os.R_OK):
            os.rename (instPath + "/etc/X11/X",
                       instPath + "/etc/X11/X.rpmsave")

        try:
            os.unlink (instPath + "/etc/X11/X")
        except OSError:
            pass
            
        os.symlink ("../../usr/X11R6/bin/Xorg",
                    instPath + "/etc/X11/X")
    else:
        fn = "/tmp/"

    id.xsetup.write(fn+"/etc/X11", id.mouse, id.keyboard)
    id.desktop.write(instPath)

def handleX11Packages(dir, intf, disp, id, instPath):

    if dir == DISPATCH_BACK:
        return
        
    # skip X setup if it is not being installed
    #
    # uncomment this block if you want X configuration to be presented
    #
# START BLOCK
#     if (not id.grpset.hdrlist.has_key('XFree86') or
#         not id.grpset.hdrlist['XFree86'].isSelected()):
#         disp.skipStep("videocard")
#         disp.skipStep("monitor")
#         disp.skipStep("xcustom")
#         disp.skipStep("writexconfig")
#         id.xsetup.skipx = 1
#     elif disp.stepInSkipList("videocard"):
#         # if X is being installed, but videocard step skipped
#         # need to turn it back on
#         disp.skipStep("videocard", skip=0)
#         disp.skipStep("monitor", skip=0)
#         disp.skipStep("xcustom", skip=0)
#         disp.skipStep("writexconfig", skip=0)
#         id.xsetup.skipx = 0
# END BLOCK

    # set default runlevel based on packages
    gnomeSelected = (id.grpset.hdrlist.has_key('gnome-session')
                     and id.grpset.hdrlist['gnome-session'].isSelected())
    gdmSelected = (id.grpset.hdrlist.has_key('gdm')
                     and id.grpset.hdrlist['gdm'].isSelected())
    kdeSelected = (id.grpset.hdrlist.has_key('kdebase')
                   and id.grpset.hdrlist['kdebase'].isSelected())
    xinstalled = ((id.grpset.hdrlist.has_key('xorg-x11')
                   and id.grpset.hdrlist['xorg-x11'].isSelected()) or
                  (id.grpset.hdrlist.has_key('XFree86')
                   and id.grpset.hdrlist['XFree86'].isSelected()))

    if gnomeSelected:
        id.desktop.setDefaultDesktop("GNOME")
    elif kdeSelected:
        id.desktop.setDefaultDesktop("KDE")

    if (gdmSelected or kdeSelected) and (xinstalled) and (not flags.serial) and (not flags.virtpconsole):
        id.desktop.setDefaultRunLevel(5)
    else:
        id.desktop.setDefaultRunLevel(3)        

# verifies that monitor is not Unprobed, and if so we can skip monitor question
def checkMonitorOK(monitor, dispatch):
    rc = 0
    if monitor is not None:
	if monitor.getMonitorID() != "Unprobed Monitor":
	    rc = 1

    dispatch.skipStep("monitor", skip=rc)

# sets a reasonable default for X settings.
def setSaneXSettings(xsetup):
    if xsetup is not None and xsetup.xhwstate is not None:
	if not xsetup.imposed_sane_default:
	    # XXX HACK see if we have a user specified LCD display
	    import re
	    
	    regx = re.compile("LCD Panel .*x.*")
	    monid = xsetup.xhwstate.monitor.getMonitorID()
	    lcdres = None
	    if regx.match(monid):
		for testres in ["640x480", "800x600", "1024x480", "1024x768",
				"1280x960", "1280x1024", "1400x1050",
				"1600x1200"]:
		    if string.find(monid, testres) != -1:
			lcdres = testres
			break
		
	    if lcdres is not None:
		xsetup.xhwstate.set_resolution(lcdres)
	    else:
		xsetup.xhwstate.choose_sane_default()
		xsetup.imposed_sane_default = 1
	    
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
    if flags.test:
	return
    
    os.environ["TZ"] = timezone.tz
    tzfile = "/usr/share/zoneinfo/" + timezone.tz
    if not os.access(tzfile, os.R_OK):
        log.error("unable to set timezone")
    else:
        try:
            iutil.copyFile(tzfile, "/etc/localtime")
        except OSError, (errno, msg):
            log.error("Error copying timezone (from %s): %s" %(tzfile, msg))

    if iutil.getArch() == "s390":
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

# do miscellaneous package selections based on other installation selections
def handleMiscPackages(intf, id, dir):
    if dir == DISPATCH_BACK:
        return

    arch = iutil.getArch ()

    # this is a crappy hack, but I don't want bug reports from these people
    if (arch == "i386") and (not id.grpset.hdrlist.has_key("kernel")):
        intf.messageWindow(_("Error"),
                           _("You are trying to install on a machine "
                             "which isn't supported by this release of "
                             "%s.") %(productName,),
                           type="custom", custom_icon="error",
                           custom_buttons=[_("_Exit")])
        sys.exit(0)

    # shorthand
    upgrade = id.getUpgrade()

    def select(hdrlist, name):
        if hdrlist.has_key(name):
            hdrlist[name].select(isManual = 1)
            return 1
        return 0

    def selected(hdrlist, name):
        if hdrlist.has_key(name) and hdrlist[name].isSelected():
            return 1
        return 0

    if not upgrade:
        foundkernel = 0
	if isys.smpAvailable() or isys.htavailable():
            if id.grpset.hdrlist.has_key("kernel-smp") and \
               id.grpset.hdrlist["kernel-smp"][rpm.RPMTAG_ARCH] == \
               id.grpset.hdrlist["kernel"][rpm.RPMTAG_ARCH]:
                if select(id.grpset.hdrlist, 'kernel-smp'):
                    foundkernel = 1
                    if selected(id.grpset.hdrlist, "gcc"):
                        select(id.grpset.hdrlist, "kernel-smp-devel")

        if foundkernel == 0:
            # we *always* need to have some sort of kernel installed
            select(id.grpset.hdrlist, 'kernel')
            
        if (selected(id.grpset.hdrlist, "gcc") and
            selected(id.grpset.hdrlist, "kernel")):
            select(id.grpset.hdrlist, "kernel-devel")

	# if NIS is configured, install ypbind and dependencies:
	if id.auth.find("--enablenis") != -1:
            select(id.grpset.hdrlist, 'ypbind')
            select(id.grpset.hdrlist, 'yp-tools')
            select(id.grpset.hdrlist, 'portmap')

	if id.auth.find("--enableldap") != -1:
            select(id.grpset.hdrlist, 'nss_ldap')
            select(id.grpset.hdrlist, 'openldap')
            select(id.grpset.hdrlist, 'perl')

	if id.auth.find("--enablekrb5") != -1:
            select(id.grpset.hdrlist, 'pam_krb5')
            select(id.grpset.hdrlist, 'krb5-workstation')
            select(id.grpset.hdrlist, 'krbafs')
            select(id.grpset.hdrlist, 'krb5-libs')

	if id.auth.find("--enablesmbauth") != -1:
            select(id.grpset.hdrlist, 'pam_smb')

        if iutil.getArch() == "i386" and id.bootloader.useGrubVal == 1:
            select(id.grpset.hdrlist, 'grub')
        elif iutil.getArch() == "s390":
            select(id.grpset.hdrlist, 's390utils')
        elif iutil.getArch() == "ppc":
            select(id.grpset.hdrlist, 'yaboot')
        elif iutil.getArch() == "ia64":
            select(id.grpset.hdrlist, 'elilo')

        if pcmcia.pcicType():
            select(id.grpset.hdrlist, 'pcmcia-cs')

        for entry in id.fsset.entries:
            for pkg in entry.fsystem.getNeededPackages():
                if select(id.grpset.hdrlist, pkg):
                    log.info("Needed %s for %s" %(pkg, entry.getMountPoint()))

def doPostInstall(method, id, intf, instPath):
    if flags.test:
	return

    w = intf.progressWindow(_("Post Install"),
                            _("Performing post install configuration..."), 6)

    upgrade = id.getUpgrade()
    arch = iutil.getArch ()

    if upgrade:
	logname = '/root/upgrade.log'
    else:
	logname = '/root/install.log'

    instLogName = instPath + logname
    instLog = open(instLogName, "a")
    
    try:
	if not upgrade:
	    w.set(1)

	    copyExtraModules(instPath, id.grpset, id.extraModules)

	    w.set(2)

	    # pcmcia is supported only on i386 at the moment
	    if arch == "i386":
		pcmcia.createPcmciaConfig(
			instPath + "/etc/sysconfig/pcmcia")

            # we need to write out the network bits before kudzu runs
            # to avoid getting devices in the wrong order (#102276)
            id.network.write(instPath)
		       
	    w.set(3)

	    # blah.  If we're on a serial mouse, and we have X, we need to
	    # close the mouse device, then run kudzu, then open it again.

	    # turn it off
	    mousedev = None

	    # XXX currently Bad Things (X async reply) happen when doing
	    # Mouse Magic on Sparc (Mach64, specificly)
	    # The s390 doesn't even have a mouse!
            if os.environ.get('DISPLAY') == ':1' and arch != 'sparc':
		try:
                    import xmouse
		    mousedev = xmouse.get()[0]
		except RuntimeError:
		    pass

	    if mousedev:
		try:
		    os.rename (mousedev, "/dev/disablemouse")
		except OSError:
		    pass
		try:
		    xmouse.reopen()
		except RuntimeError:
		    pass

	    if arch != "s390" and flags.setupFilesystems:
		# we need to unmount usbdevfs before mounting it
		usbWasMounted = iutil.isUSBDevFSMounted()
		if usbWasMounted:
                    isys.umount('/proc/bus/usb', removeDir = 0)

		    # see if unmount suceeded, if not pretent it isnt mounted
		    # because we're screwed anywyas if system is going to
		    # lock up
		    if iutil.isUSBDevFSMounted():
			usbWasMounted = 0
		    
                unmountUSB = 0
                try:
                    isys.mount('/usbfs', instPath+'/proc/bus/usb', 'usbfs')
                    unmountUSB = 1
                except:
                    log.error("Mount of /proc/bus/usb in chroot failed")
                    pass

                argv = [ "/usr/sbin/kudzu", "-q" ]
                if id.grpset.hdrlist.has_key("kernel"):
                    ver = "%s-%s" %(id.grpset.hdrlist["kernel"][rpm.RPMTAG_VERSION],
                                    id.grpset.hdrlist["kernel"][rpm.RPMTAG_RELEASE])
                    argv.extend(["-k", ver])
                
                devnull = os.open("/dev/null", os.O_RDWR)
                iutil.execWithRedirect(argv[0], argv, root = instPath,
                                       stdout = devnull)
                # turn it back on            
                if mousedev:
                    try:
                        os.rename ("/dev/disablemouse", mousedev)
                    except OSError:
                        pass
                    try:
                        xmouse.reopen()
                    except RuntimeError:
                        pass

                if unmountUSB:
                    try:
                        isys.umount(instPath + '/proc/bus/usb', removeDir = 0)
                    except SystemError:
                        # if we fail to unmount, then we should just not
                        # try to remount it.  this protects us from random
                        # suckage
                        usbWasMounted = 0

		if usbWasMounted:
                    isys.mount('/usbfs', '/proc/bus/usb', 'usbfs')

	w.set(4)

        if upgrade and id.dbpath is not None:
            # remove the old rpmdb
	    try:
		iutil.rmrf (id.dbpath)
	    except OSError:
		pass

        if upgrade:
	    # needed for prior systems which were not xinetd based
	    migrateXinetd(instPath, instLogName)

            # needed for prior to 2.6 so that mice have some chance
            # of working afterwards. FIXME: this is a hack
            migrateMouseConfig(instPath, instLogName)

        #if id.grpset.hdrlist.has_key("rhgb") and id.grpset.hdrlist["rhgb"].isSelected():
        #    log.info("rhgb installed, adding to boot loader config")
        #   id.bootloader.args.append("rhgb quiet")

        w.set(5)

        w.set(6)


    finally:
	pass

    if upgrade:
        instLog.write(_("\n\nThe following packages were available in "
                        "this version but NOT upgraded:\n"))
    else:
        instLog.write(_("\n\nThe following packages were available in "
                        "this version but NOT installed:\n"))
        
    # XXX hack - we should really write a proper lvm "config".  but for now
    # just vgscan if they have /sbin/lvm and some appearance of volumes
    if (os.access(instPath + "/sbin/lvm", os.X_OK) and
        os.access(instPath + "/dev/mapper", os.X_OK) and
        len(os.listdir("/dev/mapper")) > 1):
        rc = iutil.execWithRedirect("/sbin/lvm",
                                    ["lvm", "vgscan", "-v"],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5",
                                    root = instPath,
                                    searchPath = 1)

    # write out info on install method used
    try:
	if id.methodstr is not None:
	    if os.access (instPath + "/etc/sysconfig/installinfo", os.R_OK):
		os.rename (instPath + "/etc/sysconfig/installinfo",
			   instPath + "/etc/sysconfig/installinfo.rpmsave")

	    f = open(instPath + "/etc/sysconfig/installinfo", "w+")
	    f.write("INSTALLMETHOD=%s\n" % (string.split(id.methodstr, ':')[0],))

	    try:
		ii = open("/tmp/isoinfo", "r")
		il = ii.readlines()
		ii.close()
		for line in il:
		    f.write(line)
	    except:
		pass
	    f.close()
	else:
	    log.warning("methodstr not set for some reason")
    except:
	log.error("Failed to write out installinfo")
        
    w.pop ()

    sys.stdout.flush()
    
    if flags.setupFilesystems:
	syslog.stop()

# FIXME: this is a huge gross hack.  hard coded list of files
# created by anaconda so that we can not be killed by selinux
def setFileCons(instPath, partitions):
    import partRequests
    
    if flags.selinux:
        log.info("setting SELinux contexts for anaconda created files")

        files = ["/etc/rpm/platform", "/etc/rpm/macros",
                 "/etc/lilo.conf.anaconda",
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
            arch = grpset.hdrlist[pkg][rpm.RPMTAG_ARCH]
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

            arch = grpset.hdrlist[pkg][rpm.RPMTAG_ARCH]
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

def betaNagScreen(intf, dir):
    publicBetas = { "Red Hat Linux": "Red Hat Linux Public Beta",
                    "Red Hat Enterprise Linux": "Red Hat Enterprise Linux Public Beta",
                    "Fedora Core": "Fedora Core" }

    
    if dir == DISPATCH_BACK:
	return DISPATCH_NOOP

    fileagainst = None
    for (key, val) in publicBetas.items():
        if productName.startswith(key):
            fileagainst = val
    if fileagainst is None:
        fileagainst = "%s Beta" %(productName,)
    
    while 1:
	rc = intf.messageWindow( _("Warning! This is pre-release software!"),
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
	    rc = intf.messageWindow( _("Rebooting System"),
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
