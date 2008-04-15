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
from hdrlist import PKGTYPE_MANDATORY, PKGTYPE_DEFAULT, DependencyChecker
from installmethod import FileCopyException

from rhpl.log import log
from rhpl.translate import _
import rhpl.arch

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

def doPostAction(id, instPath):
    id.instClass.postAction(instPath, flags.serial)

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
    log("Writing main configuration")
    if not flags.test:
        id.write(instPath)

def writeKSConfiguration(id, instPath):
    log("Writing autokickstart file")
    if not flags.test:
	fn = instPath + "/root/anaconda-ks.cfg"
    else:
	fn = "/tmp/anaconda-ks.cfg"

    id.writeKS(fn)

def copyAnacondaLogs(instPath):
    log("Copying anaconda logs")
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

    xserver = id.videocard.primaryCard().getXServer()
    if not xserver:
	return

    log("Writing X configuration")
    if not testmode:
        fn = instPath

        if os.access (instPath + "/etc/X11/X", os.R_OK):
            os.rename (instPath + "/etc/X11/X",
                       instPath + "/etc/X11/X.rpmsave")

        try:
            os.unlink (instPath + "/etc/X11/X")
        except OSError:
            pass
            
        os.symlink ("../../usr/X11R6/bin/" + xserver,
			    instPath + "/etc/X11/X")
    else:
        fn = "/tmp/"

    id.xsetup.write(fn+"/etc/X11", id.mouse, id.keyboard)
    id.desktop.write(instPath)

def readPackages(intf, method, id):
    if id.grpset:
        grpset = id.grpset
        hdrlist = id.grpset.hdrlist
        doselect = 0
    else:
        grpset = None
        hdrlist = None
        doselect = 1
        
    while hdrlist is None:
	w = intf.waitWindow(_("Reading"), _("Reading package information..."))
        try:
            hdrlist = method.readHeaders()
        except FileCopyException:
            w.pop()
            method.unmountCD()
            intf.messageWindow(_("Error"),
                               _("Unable to read header list.  This may be "
                                 "due to a missing file or bad media.  "
                                 "Press <return> to try again."))
            continue

        w.pop()

    while grpset is None:
        try:
            grpset = method.readComps(hdrlist)
        except FileCopyException:
            method.unmountCD()            
            intf.messageWindow(_("Error"),
                               _("Unable to read comps file.  This may be "
                                 "due to a missing file or bad media.  "
                                 "Press <return> to try again."))
            continue

    # people make bad tree copies all the time.  let's just mandate that
    # the Core group has to exist in the comps file else we complain
    if not grpset.groups.has_key("core"):
        intf.messageWindow(_("Error"),
                           _("The comps file in your installation tree is "
                             "missing critical groups.  Please ensure that "
                             "your install tree has been correctly "
                             "generated."),
                           type="custom", custom_icon="error",
                           custom_buttons=[_("_Exit")])
        sys.exit(0)

    while iutil.getArch() == "ia64":
        try:
            method.mergeFullHeaders(hdrlist)
            break
        except FileCopyException:
            method.unmountCD()
            intf.messageWindow(_("Error"),
                               _("Unable to merge header list.  This may be "
                                 "due to a missing file or bad media.  "
                                 "Press <return> to try again."))

    # this is a crappy hack, but I don't want bug reports from these people
    if (iutil.getArch() == "i386") and (not grpset.hdrlist.has_key("kernel")):
        intf.messageWindow(_("Error"),
                           _("You are trying to install on a machine "
                             "which isn't supported by this release of "
                             "%s.") %(productName,),
                           type="custom", custom_icon="error",
                           custom_buttons=[_("_Exit")])
        sys.exit(0)
        
    id.grpset = grpset

    if doselect:
        id.instClass.setGroupSelection(grpset, intf)
        id.instClass.setPackageSelection(hdrlist, intf)

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
	    
def getAnacondaTS(instPath = None):
    if instPath:
        ts = rpm.TransactionSet(instPath)
    else:
        ts = rpm.TransactionSet()
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA))
    ts.setFlags(rpm.RPMTRANS_FLAG_ANACONDA)

    # set color if needed.  FIXME: why isn't this the default :/
    if (rhpl.arch.canonArch.startswith("ppc64") or
        rhpl.arch.canonArch in ("s390x", "sparc64", "x86_64", "ia64")):
        ts.setColor(3)

    return ts

def checkDependencies(dir, intf, disp, id, instPath):
    if dir == DISPATCH_BACK:
	return

    win = intf.waitWindow(_("Dependency Check"),
      _("Checking dependencies in packages selected for installation..."))

    # FIXME: we really don't need to build up a ts more than once
    # granted, this is better than before still
    if id.upgrade.get():
        ts = getAnacondaTS(instPath)
        how = "u"
    else:
        ts = getAnacondaTS()        
        how = "i"

    # set the rpm log file to /dev/null so that we don't segfault
    f = open("/dev/null", "w+")
    rpm.setLogFile(f)
    ts.scriptFd = f.fileno()
    
    for p in id.grpset.hdrlist.pkgs.values():
        if p.isSelected():
            ts.addInstall(p.hdr, p.hdr, how)
    depcheck = DependencyChecker(id.grpset, how)
    id.dependencies = ts.check(depcheck.callback)

    win.pop()

    if depcheck.added and id.handleDeps == CHECK_DEPS:
	disp.skipStep("dependencies", skip = 0)
        log("had unresolved dependencies, resolved.")
	disp.skipStep("dependencies")
    else:
	disp.skipStep("dependencies")

    return
    # FIXME: I BROKE IT
    # this is kind of hackish, but makes kickstart happy
    if id.handleDeps == CHECK_DEPS:
        pass
    elif id.handleDeps == IGNORE_DEPS:
        id.comps.selectDepCause(id.dependencies)
        id.comps.unselectDeps(id.dependencies)
    elif id.handleDeps == RESOLVE_DEPS:
        id.comps.selectDepCause(id.dependencies)        
        id.comps.selectDeps(id.dependencies)

class InstallCallback:
    def packageDownloadCB(self, state,  amount):
	self.progress.setPackageStatus(state, amount)
    
    def cb(self, what, amount, total, h, (param)):
	# first time here means we should pop the window telling
	# user to wait until we get here
	if not self.beenCalled:
	    self.beenCalled = 1
	    self.initWindow.pop()

	if (what == rpm.RPMCALLBACK_TRANS_START):
	    # step 6 is the bulk of the transaction set
	    # processing time
	    if amount == 6:
		self.progressWindow = \
		   self.progressWindowClass (_("Processing"),
					     _("Preparing to install..."),
					     total)
                try:
                    self.incr = total / 10
                except:
                    pass
	if (what == rpm.RPMCALLBACK_TRANS_PROGRESS):
            if self.progressWindow and amount > self.lastprogress + self.incr:
		self.progressWindow.set (amount)
                self.lastprogress = amount
		
	if (what == rpm.RPMCALLBACK_TRANS_STOP and self.progressWindow):
	    self.progressWindow.pop ()

	if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
	    # We don't want to start the timer until we get to the first
	    # file.
	    self.pkgTimer.start()

	    self.progress.setPackage(h)
	    self.progress.setPackageScale(0, 1)
	    self.instLog.write (self.modeText % (h[rpm.RPMTAG_NAME],
                                                 h[rpm.RPMTAG_VERSION],
                                                 h[rpm.RPMTAG_RELEASE],
                                                 h[rpm.RPMTAG_ARCH]))
	    self.instLog.flush ()

	    self.rpmFD = -1
            self.size = h[rpm.RPMTAG_SIZE]

	    while self.rpmFD < 0:
		try:
                    fn = self.method.getRPMFilename(h, self.pkgTimer,
			 callback=self.packageDownloadCB)
		    self.rpmFD = os.open(fn, os.O_RDONLY)

                    # Make sure this package seems valid
                    try:
                        hdr = self.ts.hdrFromFdno(self.rpmFD)
                        os.lseek(self.rpmFD, 0, 0)
                    
                        # if we don't have a valid package, throw an error
                        if not hdr:
                            raise SystemError

		    except:
			try:
			    os.close(self.rpmFD)
			except:
			    pass
			self.rpmFD = -1
			raise FileCopyException
		except Exception, e:
                    log("exception was %s for %s-%s-%s" %(e, h['name'],
                                                          h['version'],
                                                          h['release']))
                                                          
                    self.method.unmountCD()
		    self.messageWindow(_("Error"),
			_("The package %s-%s-%s cannot be opened. This is due "
                          "to a missing file or perhaps a corrupt package.  "
                          "If you are installing from CD media this usually "
			  "means the CD media is corrupt, or the CD drive is "
			  "unable to read the media.\n\n"
			  "Press <return> to try again.") % (h['name'],
                                                             h['version'],
                                                             h['release']))
	    self.progress.setPackageStatus(_("Installing..."), None)
	    fn = self.method.unlinkFilename(fn)
	    return self.rpmFD
	elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	    # RPM returns strange values sometimes
            if amount > total:
                amount = total
            if not total or total == 0 or total == "0":
                total = amount
            self.progress.setPackageScale(amount, total)
	elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
	    os.close (self.rpmFD)
	    self.progress.completePackage(h, self.pkgTimer)
	    self.progress.processEvents()
        elif ((what == rpm.RPMCALLBACK_UNPACK_ERROR) or
              (what == rpm.RPMCALLBACK_CPIO_ERROR)):
            # we may want to make this error more fine-grained at some
            # point
            pkg = "%s-%s-%s" % (h[rpm.RPMTAG_NAME],
                                h[rpm.RPMTAG_VERSION],
                                h[rpm.RPMTAG_RELEASE])
            self.messageWindow(_("Error Installing Package"),
                               _("There was an error installing %s.  This "
                                 "can indicate media failure, lack of disk "
                                 "space, and/or hardware problems.  This is "
                                 "a fatal error and your install will be "
                                 "aborted.  Please verify your media and try "
                                 "your install again.\n\n"
                                 "Press the OK button to reboot "
                                 "your system.") % (pkg,))
            sys.exit(0)
	else:
	    pass

	self.progress.processEvents()

    def __init__(self, messageWindow, progress, pkgTimer, method,
		 progressWindowClass, instLog, modeText, ts):
	self.messageWindow = messageWindow
	self.progress = progress
	self.pkgTimer = pkgTimer
	self.method = method
	self.progressWindowClass = progressWindowClass
	self.progressWindow = None
        self.lastprogress = 0
        self.incr = 20
	self.instLog = instLog
	self.modeText = modeText
	self.beenCalled = 0
	self.initWindow = None
        self.ts = ts

def sortPackages(first, second):
    # install packages in cd order (cd tag is 1000002)
    one = None
    two = None

    if first[1000003] != None:
	one = first[1000003]

    if second[1000003] != None:
	two = second[1000003]

    if one == None or two == None:
	one = 0
	two = 0
	if first[1000002] != None:
	    one = first[1000002]

	if second[1000002] != None:
	    two = second[1000002]

    if one < two:
	return -1
    elif one > two:
	return 1
    elif (string.lower(first[rpm.RPMTAG_NAME])
          < string.lower(second[rpm.RPMTAG_NAME])):
	return -1
    elif (string.lower(first[rpm.RPMTAG_NAME])
          > string.lower(second[rpm.RPMTAG_NAME])):
	return 1

    return 0

class rpmErrorClass:

    def cb(self):
	self.f.write (rpm.errorString () + "\n")

    def __init__(self, f):
	self.f = f

def doMigrateFilesystems(dir, thefsset, diskset, upgrade, instPath):
    if dir == DISPATCH_BACK:
        return DISPATCH_NOOP

    if thefsset.haveMigratedFilesystems():
        return DISPATCH_NOOP

    thefsset.migrateFilesystems (instPath)

    # if we're upgrading, we may need to do lvm device node hackery
    if upgrade.get():
        thefsset.makeLVMNodes(instPath, trylvm1 = 1)
    

def turnOnFilesystems(dir, thefsset, diskset, partitions, upgrade, instPath):
    if dir == DISPATCH_BACK:
        log("unmounting filesystems")
	thefsset.umountFilesystems(instPath)
	return

    if flags.setupFilesystems:
	if not upgrade.get():
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
    if upgrade.get() or (dir == DISPATCH_BACK):
        return

    # dont do this in test mode!
    if flags.test:
	return
    
    os.environ["TZ"] = timezone.tz
    tzfile = "/usr/share/zoneinfo/" + timezone.tz
    if not os.access(tzfile, os.R_OK):
        log("unable to set timezone")
    else:
        try:
            iutil.copyFile(tzfile, "/etc/localtime")
        except OSError, (errno, msg):
            log("Error copying timezone (from %s): %s" %(tzfile, msg))

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
        log("Failed to set clock")
    
            

def doPreInstall(method, id, intf, instPath, dir):
    if dir == DISPATCH_BACK:
        for d in ("/selinux", "/dev"):
            try:
                isys.umount(instPath + d, removeDir = 0)
            except Exception, e:
                log("unable to unmount %s: %s" %(d, e))
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
    upgrade = id.upgrade.get()

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
        xenkernel = 0

        if os.path.exists("/proc/xen/capabilities") and \
               select(id.grpset.hdrlist, "kernel-xenU"):
            log("selected xenU kernel")
            foundKernel = 1
            xenkernel = 1
            if selected(id.grpset.hdrlist, "gcc"):
                select(id.grpset.hdrlist, "kernel-xenU-devel")
        
        nthreads = isys.acpicpus()

        if nthreads == 0:
            # this should probably be table driven or something...
            ncpus = isys.smpAvailable() or 1
            nthreads = isys.htavailable() or 1
            ncores = isys.coresavailable()

            if ncpus == 1: # machines that have one socket
                nthreads = nthreads;
            else: # machines with more than one socket
                nthreads = (int(nthreads / ncores) or 1) * ncpus

        largesmp_min = -1
        if iutil.getArch() == "x86_64":
            largesmp_min = 8
        elif iutil.getArch() == "ppc" and iutil.getPPCMachine() != "iSeries":
            largesmp_min = 64
        elif iutil.getArch() == "ia64":
            largesmp_min = 64

        if not xenkernel and largesmp_min > 0 and nthreads > largesmp_min and \
                select(id.grpset.hdrlist, "kernel-largesmp"):
            foundKernel = 1
            if selected(id.grpset.hdrlist, "gcc"):
                select(id.grpset.hdrlist, "kernel-largesmp-devel")
        elif not xenkernel and nthreads > 1:
            if select(id.grpset.hdrlist, "kernel-smp"):
                foundkernel = 1
                if selected(id.grpset.hdrlist, "gcc"):
                    select(id.grpset.hdrlist, "kernel-smp-devel")

        if not xenkernel and iutil.needsEnterpriseKernel():
            if select(id.grpset.hdrlist, "kernel-bigmem"):
                foundkernel = 1

        if not xenkernel and isys.summitavailable():
            if select(id.grpset.hdrlist, "kernel-summit"):
                foundkernel = 1

        if foundkernel == 0:
            # we *always* need to have some sort of kernel installed
            select(id.grpset.hdrlist, 'kernel')

        if xenkernel: 
            log("deselecting kernel since we're installing xen kerenl")
            # XXX: this is a bit of a hack, but we can't do much better
            # with the rhel4 anaconda
            id.grpset.hdrlist["kernel"].manual_state = -2 # MANUAL_OFF
            
        if (selected(id.grpset.hdrlist, "gcc") and
            selected(id.grpset.hdrlist, "kernel")):
            select(id.grpset.hdrlist, "kernel-devel")

	# if NIS is configured, install ypbind and dependencies:
	if id.auth.useNIS:
            select(id.grpset.hdrlist, 'ypbind')
            select(id.grpset.hdrlist, 'yp-tools')
            select(id.grpset.hdrlist, 'portmap')

	if id.auth.useLdap:
            select(id.grpset.hdrlist, 'nss_ldap')
            select(id.grpset.hdrlist, 'openldap')
            select(id.grpset.hdrlist, 'perl')

	if id.auth.useKrb5:
            select(id.grpset.hdrlist, 'pam_krb5')
            select(id.grpset.hdrlist, 'krb5-workstation')
            select(id.grpset.hdrlist, 'krbafs')
            select(id.grpset.hdrlist, 'krb5-libs')

        if id.auth.useSamba:
            select(id.grpset.hdrlist, 'pam_smb')

        if iutil.getArch() == "i386" and id.bootloader.useGrubVal == 0:
            select(id.grpset.hdrlist, 'lilo')
        elif iutil.getArch() == "i386" and id.bootloader.useGrubVal == 1:
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
                    log("Needed %s for %s" %(pkg, entry.getMountPoint()))

    if flags.test:
	return

    # make sure that all comps that include other comps are
    # selected (i.e. - recurse down the selected comps and turn
    # on the children
    while 1:
        try:
            method.mergeFullHeaders(id.grpset.hdrlist)
        except FileCopyException:
            method.unmountCD()
            intf.messageWindow(_("Error"),
                               _("Unable to merge header list.  This may be "
                                 "due to a missing file or bad media.  "
                                 "Press <return> to try again."))
        else:
            break

    if upgrade:
	# An old mtab can cause confusion (esp if loop devices are
	# in it)
	f = open(instPath + "/etc/mtab", "w+")
	f.close()

        # we really started writing modprobe.conf out before things were
        # all completely ready.  so now we need to nuke old modprobe.conf's
        # if you're upgrading from a 2.4 dist so that we can get the
        # transition right
        if (os.path.exists(instPath + "/etc/modules.conf") and
            os.path.exists(instPath + "/etc/modprobe.conf") and
            not os.path.exists(instPath + "/etc/modprobe.conf.anacbak")):
            log("renaming old modprobe.conf -> modprobe.conf.anacbak")
            os.rename(instPath + "/etc/modprobe.conf",
                      instPath + "/etc/modprobe.conf.anacbak")
            

    if method.systemMounted (id.fsset, instPath):
	id.fsset.umountFilesystems(instPath)
	return DISPATCH_BACK

    for i in ( '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
	       '/etc/sysconfig', '/etc/sysconfig/network-scripts',
	       '/etc/X11', '/root', '/var/tmp', '/etc/rpm', 
               '/var/lock', '/var/lock/rpm' ):
	try:
	    os.mkdir(instPath + i)
	except os.error, (errno, msg):
            pass
#            log("Error making directory %s: %s" % (i, msg))


    if flags.setupFilesystems:
        # setup /etc/rpm/platform for the post-install environment
        iutil.writeRpmPlatform(instPath)
        
	try:
            # FIXME: making the /var/lib/rpm symlink here is a hack to
            # workaround db->close() errors from rpm
            iutil.mkdirChain("/var/lib")
            for path in ("/var/tmp", "/var/lib/rpm"):
                if os.path.exists(path) and not os.path.islink(path):
                    iutil.rmrf(path)
                if not os.path.islink(path):
                    os.symlink("/mnt/sysimage/%s" %(path,), "%s" %(path,))
                else:
                    log("%s already exists as a symlink to %s" %(path, os.readlink(path),))
	except Exception, e:
	    # how this could happen isn't entirely clear; log it in case
	    # it does and causes problems later
	    log("error creating symlink, continuing anyway: %s" %(e,))

        # SELinux hackery (#121369)
        if flags.selinux:
            try:
                os.mkdir(instPath + "/selinux")
            except Exception, e:
                pass
            try:
                isys.mount("/selinux", instPath + "/selinux", "selinuxfs")
            except Exception, e:
                log("error mounting selinuxfs: %s" %(e,))

        # we need to have a /dev during install and now that udev is
        # handling /dev, it gets to be more fun.  so just bind mount the
        # installer /dev
        if not id.grpset.hdrlist.has_key("dev"):
            log("no dev package, going to bind mount /dev")
            isys.mount("/dev", "/mnt/sysimage/dev", bindMount = 1)

    # try to copy the comps package.  if it doesn't work, don't worry about it
    try:
        id.compspkg = method.copyFileToTemp("%s/base/comps.rpm" % (productPath,))
    except:
        log("Unable to copy comps package")
        id.compspkg = None

    # write out the fstab
    if not upgrade:
        id.fsset.write(instPath)
        # rootpath mode doesn't have this file around
        if os.access("/tmp/modprobe.conf", os.R_OK):
            iutil.copyFile("/tmp/modprobe.conf", 
                           instPath + "/etc/modprobe.conf")
        if os.access("/tmp/zfcp.conf", os.R_OK):
            iutil.copyFile("/tmp/zfcp.conf", 
                           instPath + "/etc/zfcp.conf")

    # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
    f = open(instPath + "/etc/mtab", "w+")
    f.write(id.fsset.mtab())
    f.close()

#    delay writing migrate adjusted fstab till later, in case
#    rpm transaction set determines they don't have enough space to upgrade
#    else:
#        id.fsset.migratewrite(instPath)

def doInstall(method, id, intf, instPath):
    if flags.test:
	return

    # set up dependency white outs
    import whiteout
    
    upgrade = id.upgrade.get()
    ts = getAnacondaTS(instPath)

    total = 0
    totalSize = 0
    totalFiles = 0

    if upgrade:
	how = "u"
    else:
	how = "i"
        rpm.addMacro("__dbi_htconfig", "hash nofsync %{__dbi_other} %{__dbi_perms}")

    if id.excludeDocs:
        rpm.addMacro("_excludedocs", "1")

    l = []

    for p in id.grpset.hdrlist.values():
        if p.isSelected():
            l.append(p)
    l.sort(sortPackages)

    progress = intf.progressWindow(_("Processing"),
                                   _("Preparing RPM transaction..."),
                                   len(l))


    # this is kind of a hack, but has to be done so we can have a chance
    # with broken triggers
    if upgrade and len(id.upgradeRemove) > 0:
        # simple rpm callback since erasure doesn't need anything
        def install_callback(what, bytes, total, h, user):
            pass

        for pkg in id.upgradeRemove:
            ts.addErase(pkg)

        # set the rpm log file to /dev/null so that we don't segfault
        f = open("/dev/null", "w+")
        rpm.setLogFile(f)
        ts.scriptFd = f.fileno()

        # if we hit problems, it's not like there's anything we can
        # do about it
        ts.run(install_callback, 0)

        # new transaction set
        ts.closeDB()
        del ts
        ts = getAnacondaTS(instPath)

        # we don't want to try to remove things more than once (#84221)
        id.upgradeRemove = []

    i = 0
    updcount = 0
    updintv = len(l) / 25
    for p in l:
	ts.addInstall(p.hdr, p.hdr, how)
	total = total + 1
	totalSize = totalSize + (p[rpm.RPMTAG_SIZE] / 1024)
	totalFiles = totalFiles + len(p[rpm.RPMTAG_BASENAMES])
        i = i + 1

	# HACK - dont overload progress bar with useless requests
	updcount = updcount + 1
	if updcount > updintv:
	    progress.set(i)
	    updcount = 0

    progress.pop()

    # set the rpm log file to /dev/null to start with so we don't segfault
    f = open("/dev/null", "w+")
    rpm.setLogFile(f)
    ts.scriptFd = f.fileno()

    depcheck = DependencyChecker(id.grpset)
    if not id.grpset.hdrlist.preordered():
	log ("WARNING: not all packages in hdlist had order tag")
        # have to call ts.check before ts.order() to set up the alIndex
        ts.check(depcheck.callback)
        log ("did ts.check, doing ts.order")
        ts.order()
        log ("ts.order is done")
    else:
        ts.check(depcheck.callback)

    if upgrade:
	logname = '/root/upgrade.log'
    else:
	logname = '/root/install.log'

    instLogName = instPath + logname
    try:
	iutil.rmrf (instLogName)
    except OSError:
	pass

    instLog = open(instLogName, "w+")

    # dont start syslogd if we arent creating filesystems
    if flags.setupFilesystems:
	syslogname = "%s%s.syslog" % (instPath, logname)
	try:
	    iutil.rmrf (syslogname)
	except OSError:
	    pass
	syslog.start (instPath, syslogname)
    else:
	syslogname = None

    if id.compspkg is not None:
        num = i + 1
    else:
        num = i

    if upgrade:
        instLog.write(_("Upgrading %s packages\n\n") % (num,))
    else:
        instLog.write(_("Installing %s packages\n\n") % (num,))

    ts.scriptFd = instLog.fileno ()
    log ("setting rpm logfile")
    rpm.setLogFile(instLog)
    # the transaction set dup()s the file descriptor and will close the
    # dup'd when we go out of scope

    if upgrade:
	modeText = _("Upgrading %s-%s-%s.%s.\n")
    else:
	modeText = _("Installing %s-%s-%s.%s.\n")

    log ("getting rpm error class")
    errors = rpmErrorClass(instLog)
    pkgTimer = timer.Timer(start = 0)

    id.instProgress.setSizes(total, totalSize, totalFiles)
    id.instProgress.processEvents()

    cb = InstallCallback(intf.messageWindow, id.instProgress, pkgTimer,
			 method, intf.progressWindow, instLog, modeText,
                         ts)

    # write out migrate adjusted fstab so kernel RPM can get initrd right
    if upgrade:
        id.fsset.migratewrite(instPath)
    if id.upgradeDeps:
        instLog.write(_("\n\nThe following packages were automatically\n"
                        "selected to be installed:"
                        "\n"
                        "%s"
                        "\n\n") % (id.upgradeDeps,))

    cb.initWindow = intf.waitWindow(_("Install Starting"),
				    _("Starting install process, this may take several minutes..."))

    log ("setting problem filter")
    ts.setProbFilter(~rpm.RPMPROB_FILTER_DISKSPACE)
    problems = ts.run(cb.cb, 0)

    if problems:
        # restore old fstab if we did anything for migrating
        if upgrade:
            id.fsset.restoreMigratedFstab(instPath)

	spaceneeded = {}
	nodeneeded = {}
	size = 12

	for (descr, (type, mount, need)) in problems:
            log("(%s, (%s, %s, %s))" %(descr, type, mount, need))
            if mount and mount.startswith(instPath):
		mount = mount[len(instPath):]
            if not mount:
                mount = '/'

	    if type == rpm.RPMPROB_DISKSPACE:
		if spaceneeded.has_key (mount) and spaceneeded[mount] < need:
		    spaceneeded[mount] = need
		else:
		    spaceneeded[mount] = need
	    elif type == nodeprob:
		if nodeneeded.has_key (mount) and nodeneeded[mount] < need:
		    nodeneeded[mount] = need
		else:
		    nodeneeded[mount] = need
	    else:
                if descr is None:
                    descr = "no description"
		log ("WARNING: unhandled problem returned from "
                     "transaction set type %d (%s)",
		     type, descr)

	probs = ""
	if spaceneeded:
	    probs = probs + _("You don't appear to have enough disk space "
                              "to install the packages you've selected. "
                              "You need more space on the following "
                              "file systems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"),
                                              _("Space Needed"))

	    for (mount, need) in spaceneeded.items ():
                log("(%s, %s)" %(mount, need))
		if need > (1024*1024):
		    need = (need + 1024 * 1024 - 1) / (1024 * 1024)
		    suffix = "M"
		else:
		    need = (need + 1023) / 1024
		    suffix = "k"

		prob = "%-15s %d %c\n" % (mount, need, suffix)
		probs = probs + prob
	if nodeneeded:
	    if probs:
		probs = probs + '\n'
	    probs = probs + _("You don't appear to have enough file nodes "
                              "to install the packages you've selected. "
                              "You need more file nodes on the following "
                              "file systems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"),
                                              _("Nodes Needed"))

	    for (mount, need) in nodeneeded.items ():
		prob = "%-15s %d\n" % (mount, need)
		probs = probs + prob

        if len(probs) == 0:
            probs = ("ERROR: NO!  An unexpected problem has occurred with "
                     "your transaction set.  Please see tty3 for more "
                     "information")

	intf.messageWindow (_("Disk Space"), probs)

        ts.closeDB()
	del ts
	instLog.close()

	if syslogname:
	    syslog.stop()

	method.systemUnmounted ()

	return DISPATCH_BACK

    # This should close the RPM database so that you can
    # do RPM ops in the chroot in a %post ks script
    ts.closeDB()
    del ts

    # make sure the window gets popped (#82862)
    if not cb.beenCalled:
        cb.initWindow.pop()
    
    method.filesDone ()

    # rpm environment files go bye-bye
    for file in ["__db.001", "__db.002", "__db.003"]:
        try:
            os.unlink("%s/var/lib/rpm/%s" %(instPath, file))
        except Exception, e:
            log("failed to unlink /var/lib/rpm/%s: %s" %(file,e))
    # FIXME: remove the /var/lib/rpm symlink that keeps us from having
    # db->close error messages shown.  I don't really like this though :(
    try:
        os.unlink("/var/lib/rpm")
    except Exception, e:
        log("failed to unlink /var/lib/rpm: %s" %(e,))

    instLog.close ()

    id.instProgress = None

def doPostInstall(method, id, intf, instPath):
    if flags.test:
	return

    w = intf.progressWindow(_("Post Install"),
                            _("Performing post install configuration..."), 6)

    upgrade = id.upgrade.get()
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
                    log("Mount of /proc/bus/usb in chroot failed")
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

        if id.grpset.hdrlist.has_key("rhgb") and id.grpset.hdrlist["rhgb"].isSelected():
            log("rhgb installed, adding to boot loader config")
            id.bootloader.args.append("rhgb quiet")

        w.set(5)

        # FIXME: hack to install the comps package
        if (id.compspkg is not None and
            os.access(id.compspkg, os.R_OK)):
            log("found the comps package")
            try:
                # ugly hack
                path = id.compspkg.split("/mnt/sysimage")[1]
                args = ["/bin/rpm", "-Uvh", path]
                rc = iutil.execWithRedirect(args[0], args,
                                            stdout = "/dev/tty5",
                                            stderr = "/dev/tty5",
                                            root = instPath)
                ts = rpm.TransactionSet()
                ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA))
                ts.closeDB()
                fd = os.open(id.compspkg, os.O_RDONLY)
                h = ts.hdrFromFdno(fd)
                os.close(fd)
                if upgrade:
                    text = _("Upgrading %s-%s-%s.%s.\n")
                else:
                    text = _("Installing %s-%s-%s.%s.\n")
                instLog.write(text % (h['name'],
                                      h['version'],
                                      h['release'],
                                      h['arch']))
                os.unlink(id.compspkg)
                del ts

            except Exception, e:
                log("comps.rpm failed to install: %s" %(e,))
                try:
                    os.unlink(id.compspkg)
                except:
                    pass
        else:
            log("no comps package found")
                
        w.set(6)


    finally:
	pass

    if upgrade:
        instLog.write(_("\n\nThe following packages were available in "
                        "this version but NOT upgraded:\n"))
    else:
        instLog.write(_("\n\nThe following packages were available in "
                        "this version but NOT installed:\n"))
        
    lines = []
    for p in id.grpset.hdrlist.values():
        if not p.isSelected():
            lines.append("%s-%s-%s.%s.rpm\n" %
                         (p.hdr[rpm.RPMTAG_NAME],
                          p.hdr[rpm.RPMTAG_VERSION],
                          p.hdr[rpm.RPMTAG_RELEASE],
                          p.hdr[rpm.RPMTAG_ARCH]))
    lines.sort()
    for line in lines:
        instLog.write(line)
    

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
	    log("methodstr not set for some reason")
    except:
	log("Failed to write out installinfo")
        
    w.pop ()

    sys.stdout.flush()
    
    if flags.setupFilesystems:
	syslog.stop()

# FIXME: this is a huge gross hack.  hard coded list of files
# created by anaconda so that we can not be killed by selinux
def setFileCons(instPath, partitions):
    import partRequests
    
    if flags.selinux:
        log("setting SELinux contexts for anaconda created files")

        files = ["/etc/rpm/platform", "/etc/rpm/macros",
                 "/etc/lilo.conf", "/etc/lilo.conf.anaconda",
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
                    log("%s doesn't exist" %(f,))
                    continue
                ret = isys.resetFileContext(f)
                log("set fc of %s to %s" %(f, ret))
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
	log("running: '%s'" % (command, ))
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
                    log("moving %s to %s" % (fromFile, to))
                    os.rename(fromFile, to)
                    # the file might not have been owned by root in the cgz
                    os.chown(to, 0, 0)
                    foundModule = 1
                else:
                    log("missing DD module %s (this may be okay)" % 
                        fromFile)

    if foundModule == 1:
        for (n, tag) in kernelVersions:
            recreateInitrd(n, instPath)


#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log("recreating initrd for %s" % (kernelTag,))
    iutil.execWithRedirect("/sbin/new-kernel-pkg",
                           [ "/sbin/new-kernel-pkg", "--mkinitrd",
                             "--depmod", "--install", kernelTag ],
                           stdout = None, stderr = None,
                           searchPath = 1, root = instRoot)

# XXX Deprecated.  Is this ever called anymore?
def depmodModules(comps, instPath):
    kernelVersions = comps.kernelVersionList()

    for (version, tag) in kernelVersions:
	iutil.execWithRedirect ("/sbin/depmod",
				[ "/sbin/depmod", "-a", version,
                                  "-F", "/boot/System.map-" + version ],
				root = instPath, stderr = '/dev/null')


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
				   "   http://bugzilla.redhat.com/bugzilla\n\n"
				   "and file a report against '%s'.\n"
                                   %(productName, fileagainst)),
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
def selectLanguageSupportGroups(grpset, langSupport):
    sup = langSupport.supported
    if len(sup) == 0:
        sup = langSupport.getAllSupported()

    for group in grpset.groups.values():
        xmlgrp = grpset.compsxml.groups[group.basename]
        langs = []
        for name in sup:
            try:
                lang = langSupport.langInfoByName[name][0]
                langs.extend(language.expandLangs(lang))
            except:
                continue
            
        if group.langonly is not None and group.langonly in langs:
            group.select()
            for package in xmlgrp.pkgConditionals.keys():
                req = xmlgrp.pkgConditionals[package]
                if not grpset.hdrlist.has_key(package):
                    log("Missing %s which is in a langsupport conditional" %(package,))
                    continue
                # add to the deps in the dependencies structure for the
                # package.  this should take care of whenever we're
                # selected
                grpset.hdrlist[req].addDeps([package], main = 0)
                if grpset.hdrlist[req].isSelected():
                    grpset.hdrlist[package].select()
                    sys.stdout.flush()
                    grpset.hdrlist[package].usecount += grpset.hdrlist[req].usecount - 1
                    group.selectDeps([package], uses = grpset.hdrlist[req].usecount)
    
