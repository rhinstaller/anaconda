#
# packages.py: package management - mainly package installation
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
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
from constants import *
from syslogd import syslog
from comps import PKGTYPE_MANDATORY, PKGTYPE_DEFAULT

from rhpl.log import log
from rhpl.translate import _

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

def writeXConfiguration(id, instPath):
    if flags.test:
        return

    if id.xconfig.skipx:
        return
    
    xserver = id.videocard.primaryCard().getXServer()
    if not xserver:
        return

    log("Writing X configuration")
    if not flags.test:
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

    id.xconfig.write(fn+"/etc/X11")
    id.desktop.write(instPath)

def readPackages(intf, method, id):
    if (not id.hdList):
	w = intf.waitWindow(_("Reading"), _("Reading package information..."))
	id.hdList = method.readHeaders()
	id.instClass.setPackageSelection(id.hdList)
	w.pop()

    if not id.comps:
	id.comps = method.readComps(id.hdList)
	id.instClass.setGroupSelection(id.comps)

	# XXX
	#updateInstClassComps ()
    else:
	# re-evaluate all the expressions for packages with qualifiers.

	id.comps.updateSelections()

def handleX11Packages(dir, intf, disp, id, instPath):

    if dir == DISPATCH_BACK:
        return
        
    # skip X setup if it is not being installed
    if (not id.comps.packages.has_key('XFree86') or
        not id.comps.packages['XFree86'].selected):
        disp.skipStep("videocard")
        disp.skipStep("monitor")
        disp.skipStep("xcustom")
        disp.skipStep("writexconfig")
        id.xconfig.skipx = 1
    elif disp.stepInSkipList("videocard"):
        # if X is being installed, but videocard step skipped
        # need to turn it back on
        disp.skipStep("videocard", skip=0)
        disp.skipStep("monitor", skip=0)
        disp.skipStep("xcustom", skip=0)
        disp.skipStep("writexconfig", skip=0)
        id.xconfig.skipx = 0

    # set default runlevel based on packages
    gnomeSelected = (id.comps.packages.has_key('gnome-session')
                     and id.comps.packages['gnome-session'].selected)
    kdeSelected = (id.comps.packages.has_key('kdebase')
                   and id.comps.packages['kdebase'].selected)

    if gnomeSelected:
        id.desktop.setDefaultDesktop("GNOME")
    elif kdeSelected:
        id.desktop.setDefaultDesktop("KDE")

    if gnomeSelected or kdeSelected:
        id.desktop.setDefaultRunLevel(5)

def checksig(fileName):
    # RPM spews to stdout/stderr.  Redirect.
    # stolen from up2date/up2date.py
    saveStdout = os.dup(1)
    saveStderr = os.dup(2)
    redirStdout = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
    redirStderr = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
    os.dup2(redirStdout, 1)
    os.dup2(redirStderr, 2)
    # now do the rpm thing
    ret = rpm.checksig(fileName, rpm.CHECKSIG_MD5)
    # restore normal stdout and stderr
    os.dup2(saveStdout, 1)
    os.dup2(saveStderr, 2)
    # Clean up
    os.close(redirStdout)
    os.close(redirStderr)
    os.close(saveStdout)
    os.close(saveStderr)
    return ret    

def checkDependencies(dir, intf, disp, id, instPath):
    if dir == DISPATCH_BACK:
	return

    win = intf.waitWindow(_("Dependency Check"),
      _("Checking dependencies in packages selected for installation..."))

    id.dependencies = id.comps.verifyDeps(instPath, id.upgrade.get())

    win.pop()

    if (id.dependencies and id.comps.canResolveDeps(id.dependencies)
        and id.handleDeps == CHECK_DEPS):
	disp.skipStep("dependencies", skip = 0)
    else:
	disp.skipStep("dependencies")

    # this is kind of hackish, but makes kickstart happy
    if id.handleDeps == CHECK_DEPS:
        pass
    elif id.handleDeps == IGNORE_DEPS:
        id.comps.selectDepCause(id.dependencies)
        id.comps.unselectDeps(id.dependencies)
    elif id.handleDeps == RESOLVE_DEPS:
        id.comps.selectDepCause(id.dependencies)        
        id.comps.selectDeps(id.dependencies)

#XXX
#try:
    #self.todo.getHeaderList ()
    #self.todo.getCompsList()
    #self.files_found = "TRUE"
#except ValueError, msg:
    #extra = msg
#except RuntimeError, msg:
    #extra = msg
#except TypeError, msg:
    #extra = msg
#except KeyError, key:
    #extra = ("The comps file references a package called \"%s\" which "
	     #"could not be found." % (key,))
#except:
    #extra = ""
#
#if self.files_found == "FALSE":
    #if extra:
	#text = (_("The following error occurred while "
		  #"retreiving hdlist file:\n\n"
		  #"%s\n\n"
		  #"Installer will exit now.") % extra)
    #else:
	#text = (_("An error has occurred while retreiving the hdlist "
		  #"file.  The installation media or image is "
		  #"probably corrupt.  Installer will exit now."))
    #win = ErrorWindow (text)
#else:

class InstallCallback:
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
	if (what == rpm.RPMCALLBACK_TRANS_PROGRESS):
	    if self.progressWindow:
		self.progressWindow.set (amount)
		
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
                                                 h[rpm.RPMTAG_RELEASE]))
	    self.instLog.flush ()

	    self.rpmFD = -1
            self.size = h[rpm.RPMTAG_SIZE]

	    while self.rpmFD < 0:
                fn = self.method.getFilename(h, self.pkgTimer)
#		log("Opening rpm %s", fn)
		try:
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
			raise SystemError
		except:
                    self.method.unmountCD()
		    self.messageWindow(_("Error"),
			_("The file %s cannot be opened. This is due to "
			  "a missing file, a bad package, or bad media. "
			  "Press <return> to try again.") % fn)

	    fn = self.method.unlinkFilename(fn)
	    return self.rpmFD
	elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	    # just lets make sure its defined to something
	    cur_amount = amount

	    # RPM returns strange values sometimes (dev package usually)
            if total == 100:
		cur_amount = self.size

	    # seems some packages (dev) make rpm return bogus values
	    if cur_amount > self.size:
		cur_amount = self.size
	    elif cur_amount < 0:
		cur_amount = 0

	    if self.size <= 0:
		log("Bogus size %s!", self.size)
	    else:
		self.progress.setPackageScale(cur_amount, self.size)
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
    

def turnOnFilesystems(dir, thefsset, diskset, partitions, upgrade, instPath):
    if dir == DISPATCH_BACK:
	thefsset.umountFilesystems(instPath)
	return

    if flags.setupFilesystems:
	if not upgrade.get():
            partitions.doMetaDeletes(diskset)
            thefsset.setActive(diskset)
            if not thefsset.isActive():
                diskset.savePartitions ()
            thefsset.checkBadblocks(instPath)
            thefsset.createLogicalVolumes(instPath)
            thefsset.formatSwap(instPath)
            thefsset.turnOnSwap(instPath)
	    thefsset.makeFilesystems (instPath)
            thefsset.mountFilesystems (instPath)

def doPreInstall(method, id, intf, instPath, dir):
    if flags.test:
	return

    if dir == DISPATCH_BACK:
        return

    arch = iutil.getArch ()

    # shorthand
    upgrade = id.upgrade.get()

    def select(hdList, name):
        if hdList.has_key(name):
            hdList[name].selected = 1

    if not upgrade:
	# this is NICE and LATE. It lets kickstart/server/workstation
	# installs detect this properly
        if arch == "s390":
	    if (string.find(os.uname()[2], "tape") > -1):
		select(id.hdList, 'kernel-tape')
	    else:
		select(id.hdList, 'kernel')
	elif isys.smpAvailable() or isys.htavailable():
            select(id.hdList, 'kernel-smp')

	if (id.hdList.has_key('kernel-bigmem')):
	    if iutil.needsEnterpriseKernel():
		id.hdList['kernel-bigmem'].selected = 1

	if (id.hdList.has_key('kernel-summit')):
	    if isys.summitavailable():
		id.hdList['kernel-summit'].selected = 1

	# we *always* need a kernel installed
        select(id.hdList, 'kernel')

	# if NIS is configured, install ypbind and dependencies:
	if id.auth.useNIS:
            select(id.hdList, 'ypbind')
            select(id.hdList, 'yp-tools')
            select(id.hdList, 'portmap')

	if id.auth.useLdap:
            select(id.hdList, 'nss_ldap')
            select(id.hdList, 'openldap')
            select(id.hdList, 'perl')

	if id.auth.useKrb5:
            select(id.hdList, 'pam_krb5')
            select(id.hdList, 'krb5-workstation')
            select(id.hdList, 'krbafs')
            select(id.hdList, 'krb5-libs')

        if id.auth.useSamba:
            select(id.hdList, 'pam_smb')

        if iutil.getArch() == "i386" and id.bootloader.useGrubVal == 0:
            select(id.hdList, 'lilo')
        elif iutil.getArch() == "i386" and id.bootloader.useGrubVal == 1:
            select(id.hdList, 'grub')

        if pcmcia.pcicType():
            select(id.hdList, 'kernel-pcmcia-cs')

        if iutil.getArch() != "s390":
            xserver = id.videocard.primaryCard().getXServer()
            if (xserver and id.comps.packages.has_key('XFree86')
                and id.comps.packages['XFree86'].selected
                and xserver != "XFree86"):
                try:
                    id.hdList['XFree86-' + xserver[5:]].selected = 1
                except ValueError, message:
                    log ("Error selecting XFree86 server package: %s", message)
                except KeyError:
                    log ("Error selecting XFree86 server package, "
                         "package not available")

                # XXX remove me once we have dependency resolution after
                # videocard selection
                try:
                    id.hdList['XFree86-compat-modules'].selected = 1
                except ValueError, message:
                    log ("Error selecting XFree86-compat-modules package")
                except KeyError:
                    log ("Error selecting XFree86-compat-modules, "
                         "package not available")
                
                
    # make sure that all comps that include other comps are
    # selected (i.e. - recurse down the selected comps and turn
    # on the children

    method.mergeFullHeaders(id.hdList)

    if upgrade:
	# An old mtab can cause confusion (esp if loop devices are
	# in it)
	f = open(instPath + "/etc/mtab", "w+")
	f.close()

    if method.systemMounted (id.fsset, instPath, id.hdList.selected()):
	id.fsset.umountFilesystems(instPath)
	return DISPATCH_BACK

    for i in ( '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
	       '/etc/sysconfig', '/etc/sysconfig/network-scripts',
	       '/etc/X11', '/root', '/var/tmp' ):
	try:
	    os.mkdir(instPath + i)
	except os.error, (errno, msg):
            pass
#            log("Error making directory %s: %s" % (i, msg))


    if flags.setupFilesystems:
	try:
	    if os.path.exists("/var/tmp") and not os.path.islink("/var/tmp"):
		iutil.rmrf("/var/tmp")
	    if not os.path.islink("/var/tmp"):
		os.symlink("/mnt/sysimage/var/tmp", "/var/tmp")
	    else:
		log("/var/tmp already exists as a symlink to %s" %(os.readlink("/var/tmp"),))
	except:
	    # how this could happen isn't entirely clear; log it in case
	    # it does and causes problems later
	    log("unable to create symlink for /var/tmp.  assuming already created")

    # try to copy the comps package.  if it doesn't work, don't worry about it
    try:
        id.compspkg = method.copyFileToTemp("RedHat/base/comps.rpm")
    except:
        log("Unable to copy comps package")
        id.compspkg = None

    # write out the fstab
    if not upgrade:
        id.fsset.write(instPath)
        # rootpath mode doesn't have this file around
        if os.access("/tmp/modules.conf", os.R_OK):
            iutil.copyFile("/tmp/modules.conf", 
                           instPath + "/etc/modules.conf")

    # add lines for usb to modules.conf
    # these aren't handled in the loader since usb is built into kernel
    # so we don't insert the modules there
    try:
	usbcontrollers = kudzu.probe(kudzu.CLASS_USB, kudzu.BUS_PCI, kudzu.PROBE_ALL)
    except:
	usbcontrollers = []
	
    ohcifnd = 0
    ehcifnd = 0
    for u in usbcontrollers:
	if u.driver == "usb-ohci":
	    ohcifnd = 1
	elif u.driver == "ehci-hcd":
	    ehcifnd = 1

    if ohcifnd or ehcifnd:
	f = open(instPath + "/etc/modules.conf", "a")
	if ohcifnd:
	    f.write("alias usb-controller usb-ohci\n")
	if ehcifnd:
	    if ohcifnd:
		f.write("alias usb-controller1 ehci-hcd\n")
	    else:
		f.write("alias usb-controller ehci-hcd\n")
	f.close()
	    
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
    ts = rpm.TransactionSet(instPath)

    ts.setVSFlags(~rpm.RPMVSF_NORSA|~rpm.RPMVSF_NODSA)
    ts.setFlags(rpm.RPMTRANS_FLAG_NOMD5|rpm.RPMTRANS_FLAG_CHAINSAW)

    total = 0
    totalSize = 0

    if upgrade:
	how = "u"
    else:
	how = "i"

    l = []

    for p in id.hdList.selected():
	l.append(p)
    l.sort(sortPackages)

    progress = intf.progressWindow(_("Processing"),
                                   _("Setting up RPM transaction..."),
                                   len(l))

    i = 0
    for p in l:
	ts.addInstall(p.h, p.h, how)
	total = total + 1
	totalSize = totalSize + (p[rpm.RPMTAG_SIZE] / 1024)
        i = i + 1
        progress.set(i)

    progress.pop()
    
    if not id.hdList.preordered():
	log ("WARNING: not all packages in hdlist had order tag")
        # have to call ts.check before ts.order() to set up the alIndex
        ts.check()
        ts.order()

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
    syslogname = "%s%s.syslog" % (instPath, logname)
    try:
        iutil.rmrf (syslogname)
    except OSError:
        pass
    syslog.start (instPath, syslogname)

    if upgrade:
        instLog.write(_("Upgrading %s packages\n\n") % (i))        
    else:
        instLog.write(_("Installing %s packages\n\n") % (i))

    ts.scriptFd = instLog.fileno ()
    # the transaction set dup()s the file descriptor and will close the
    # dup'd when we go out of scope

    if upgrade:
	modeText = _("Upgrading %s-%s-%s.\n")
    else:
	modeText = _("Installing %s-%s-%s.\n")

    errors = rpmErrorClass(instLog)
#    oldError = rpm.errorSetCallback (errors.cb)
    pkgTimer = timer.Timer(start = 0)

    id.instProgress.setSizes(total, totalSize)
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

    ts.setProbFilter(~rpm.RPMPROB_FILTER_DISKSPACE)
    problems = ts.run(cb.cb, 0)

    if problems:
        # restore old fstab if we did anything for migrating
        if upgrade:
            id.fsset.restoreMigratedFstab(instPath)

	spaceneeded = {}
	nodeneeded = {}
	size = 12

	# XXX
	nodeprob = -1
	if rpm.__dict__.has_key ("RPMPROB_DISKNODES"):
	    nodeprob = rpm.RPMPROB_DISKNODES

	for (descr, (type, mount, need)) in problems:
            if mount.startswith(instPath):
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
		log ("WARNING: unhandled problem returned from "
                     "transaction set type %d",
		     type)

	probs = ""
	if spaceneeded:
	    probs = probs + _("You don't appear to have enough disk space "
                              "to install the packages you've selected. "
                              "You need more space on the following "
                              "file systems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"),
                                              _("Space Needed"))

	    for (mount, need) in spaceneeded.items ():
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

	intf.messageWindow (_("Disk Space"), probs)

	del ts
	instLog.close()
	syslog.stop()

	method.systemUnmounted ()

#	rpm.errorSetCallback (oldError)
	return DISPATCH_BACK

    # This should close the RPM database so that you can
    # do RPM ops in the chroot in a %post ks script
    del ts
#    rpm.errorSetCallback (oldError)
    
    method.filesDone ()

    if upgrade:
        instLog.write(_("\n\nThe following packages were available in "
                        "this version but NOT upgraded:\n"))
	for p in id.hdList.packages.values ():
	    if not p.selected:
		instLog.write("%s-%s-%s.%s.rpm\n" %
				   (p.h[rpm.RPMTAG_NAME],
				    p.h[rpm.RPMTAG_VERSION],
				    p.h[rpm.RPMTAG_RELEASE],
				    p.h[rpm.RPMTAG_ARCH]))
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

	    copyExtraModules(instPath, id.comps, id.extraModules)

	    w.set(2)

	    # pcmcia is supported only on i386 at the moment
	    if arch == "i386":
		pcmcia.createPcmciaConfig(
			instPath + "/etc/sysconfig/pcmcia")
		       
	    w.set(3)

	    # blah.  If we're on a serial mouse, and we have X, we need to
	    # close the mouse device, then run kudzu, then open it again.

	    # turn it off
	    mousedev = None

	    # XXX currently Bad Things (X async reply) happen when doing
	    # Mouse Magic on Sparc (Mach64, specificly)
	    # The s390 doesn't even have a mouse!
	    if os.environ.has_key ("DISPLAY") and not (arch == "sparc" or arch == "s390"):
		import xmouse
		try:
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

	    if arch != "s390":
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
                    isys.mount('/usbdevfs', instPath+'/proc/bus/usb', 'usbdevfs')
                    unmountUSB = 1
                except:
                    log("Mount of /proc/bus/usb in chroot failed")
                    pass


                argv = [ "/usr/sbin/kudzu", "-q" ]
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
                    isys.umount(instPath + '/proc/bus/usb', removeDir = 0)

		if usbWasMounted:
                    isys.mount('/usbdevfs', '/proc/bus/usb', 'usbdevfs')

	w.set(4)

        if upgrade and id.dbpath is not None:
	    # move the rebuilt db into place.
	    try:
		iutil.rmrf (instPath + "/var/lib/rpm.rpmsave")
	    except OSError:
		pass
            try:
                os.rename (instPath + "/var/lib/rpm",
                           instPath + "/var/lib/rpm.rpmsave")
            except OSError:
                # XXX hack..., if the above move failed, we'll just stash it in
                # a (hopefully) unique location. (#50339)
                os.rename (instPath + "/var/lib/rpm",
                           instPath + "/var/lib/rpm.rpmsave-%s" %
                           (str(int(time.time())),))
            os.rename (instPath + id.dbpath,
		       instPath + "/var/lib/rpm")

	    # XXX - rpm 4.0.2 %post braindeadness support
	    try:
		os.unlink (instPath + "/etc/rpm/macros.db1")
	    except OSError:
		pass

        if upgrade:
	    # needed for prior systems which were not xinetd based
	    migrateXinetd(instPath, instLogName)

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
                fd = os.open(id.compspkg, os.O_RDONLY)
                h = rpm.headerFromPackage(fd)[0]
                os.close(fd)
                if upgrade:
                    text = _("Upgrading %s-%s-%s.\n")
                else:
                    text = _("Installing %s-%s-%s.\n")
                instLog.write(text % (h['name'],
                                      h['version'],
                                      h['release']))
                os.unlink(id.compspkg)

            except:
                log("failed to install comps.rpm.  oh well")
                try:
                    os.unlink(id.compspkg)
                except:
                    pass
        else:
            log("no comps package found")
                
        w.set(6)


    finally:
	pass

    # XXX hack - we should really write a proper /etc/lvmtab
    if os.access(instPath + "/sbin/vgscan", os.X_OK):
        rc = iutil.execWithRedirect("/sbin/vgscan",
                                    ["vgscan", "-v"],
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
    syslog.stop()

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

def copyExtraModules(instPath, comps, extraModules):
    kernelVersions = comps.kernelVersionList()

    for (path, subdir, name) in extraModules:
        if not path:
            path = "/modules.cgz"
	pattern = ""
	names = ""
	for (n, tag) in kernelVersions:
	    pattern = pattern + " " + n + "/" + name + ".o"
	    names = names + " " + name + ".o"
	command = ("cd %s/lib/modules; gunzip < %s | "
                   "%s/bin/cpio  --quiet -iumd %s" % 
                   (instPath, path, instPath, pattern))
	log("running: '%s'" % (command, ))
	os.system(command)

	for (n, tag) in kernelVersions:
	    fromFile = "%s/lib/modules/%s/%s.o" % (instPath, n, name)
	    toDir = "%s/lib/modules/%s/kernel/drivers/%s" % \
		    (instPath, n, subdir)
	    to = "%s/%s.o" % (toDir, name)

	    if (os.access(fromFile, os.R_OK) and 
		    os.access(toDir, os.X_OK)):
		log("moving %s to %s" % (fromFile, to))
		os.rename(fromFile, to)

		# the file might not have been owned by root in the cgz
		os.chown(to, 0, 0)
	    else:
		log("missing DD module %s (this may be okay)" % 
			    fromFile)

            recreateInitrd(n, instPath)


#Recreate initrd for use when driver disks add modules
def recreateInitrd (kernelTag, instRoot):
    log("recreating initrd for %s" % (kernelTag,))
    if iutil.getArch() == 'ia64':
        initrd = "/boot/efi/EFI/redhat/initrd-%s.img" % (kernelTag, )
    else:
        initrd = "/boot/initrd-%s.img" % (kernelTag, )

    iutil.execWithRedirect("/sbin/mkinitrd",
                           [ "/sbin/mkinitrd", "--ifneeded", "-f",
                             initrd, kernelTag ],
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
    if dir == DISPATCH_BACK:
	return DISPATCH_NOOP
    
    while 1:
	rc = intf.messageWindow( _("Warning! This is a beta!"),
				 _("Thank you for downloading this "
				   "Red Hat Beta release.\n\n"
				   "This is not a final "
				   "release and is not intended for use "
				   "on production systems.  The purpose of "
				   "this release is to collect feedback "
				   "from testers, and it is not suitable "
				   "for day to day usage.\n\n"
				   "To report feedback, please visit:\n\n"
				   "    http://bugzilla.redhat.com/bugzilla\n\n"
				   "and file a report against 'Red Hat Public "
				   "Beta'.\n"),
				   type="custom", custom_icon="warning",
				   custom_buttons=[_("_Exit"), _("_Install BETA")])

	if not rc:
	    rc = intf.messageWindow( _("Rebooting System"),
				 _("Your system will now be rebooted..."),
				 type="custom", custom_icon="warning",
				 custom_buttons=[_("_Back"), _("_Reboot")])
	    if rc:
		sys.exit(0)
	else:
	    break

# FIXME: this is a kind of poor way to do this, but it will work for now
def selectLanguageSupportGroups(comps, langSupport):
    sup = langSupport.supported
    if len(sup) == 0:
        sup = langSupport.getAllSupported()

    for group in comps.compsxml.groups.values():
        for name in sup:
            try:
                lang = langSupport.langInfoByName[name][0]
                langs = language.expandLangs(lang)
            except:
                continue
            if group.langonly in langs:
                if not comps.compsDict.has_key(group.name):
                    log("Where did the %s component go?"
                        %(group.name,))
                    continue
                comps.compsDict[group.name].select()
                for package in group.pkgConditionals.keys():
                    req = group.pkgConditionals[package]
                    if not comps.packages.has_key(package):
                        log("Missing %s which is in a langsupport conditional" %(package,))
                        continue
                    if not comps.compsxml.packages.has_key(req):
                        log("Missing %s which is required by %s in a langsupport group" %(req, package))
                        continue
                    # add to the deps in the dependencies structure --
                    # this will take care of if we're ever added as a dep
                    comps.compsxml.packages[req].dependencies.append(package)
                    # also add to components as needed
                    # if the req is PKGTYPE_MANDATORY, then just add to the
                    # depsDict.  if the req is PKGTYPE_DEFAULT, add it
                    # as DEFAULT
                    pkg = comps.packages[package]
                    for comp in comps.packages[req].comps:
                        if comp.newpkgDict.has_key(req):
                            if comp.newpkgDict[req][0] == PKGTYPE_MANDATORY:
                                comp.addDependencyPackage(pkg)
                            else:
                                comp.addPackage(pkg, PKGTYPE_DEFAULT)
                        elif comp.depsDict.has_key(req):
                            comp.addDependencyPackage(pkg)
    comps.updateSelections()
