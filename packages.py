#
# packages.py: package management - mainly package installation
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from translate import _
import iutil
import isys
import rpm
import os
import timer
import sys
import string
import pcmcia
import dispatch
from log import log
from flags import flags

def queryUpgradeContinue(intf, dir, dispatch):
    if dir == dispatch.DISPATCH_BACK:
        return

    rc = intf.messageWindow(_("Proceed with upgrade?"),
                       _("The filesystems of the Linux installation "
                         "you have chosen to upgrade have already been "
                         "mounted. You cannot go back past this point. "
                         "\n\n") + 
                     _( "Would you like to continue with the upgrade?"),
                                      type = "yesno").getrc()
    if rc == 1:
        sys.exit(0)
    dispatch.gotoNext()

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
        print "linked ../../usr/X11R6/bin/",xserver," to ",instPath,"/etc/X11/X"
    else:
        fn = "/tmp/"

    id.xconfig.write(fn+"/etc/X11")

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

    if dir == dispatch.DISPATCH_BACK:
        return
        
    # skip X setup if it is not being installed
    if (not id.comps.packages.has_key('XFree86') or
        not id.comps.packages['XFree86'].selected):
        disp.skipStep("videocard")
        disp.skipStep("monitor")
        disp.skipStep("xcustom")
        disp.skipStep("writexconfig")
    elif disp.stepInSkipList("videocard"):
        # if X is being installed, but videocard step skipped
        # need to turn it back on
        disp.skipStep("videocard", skip=0)
        disp.skipStep("monitor", skip=0)
        disp.skipStep("xcustom", skip=0)
        disp.skipStep("writexconfig", skip=0)

    # set default runlevel based on packages
    gnomeSelected = (id.comps.packages.has_key('gnome-core')
                     and id.comps.packages['gnome-core'].selected)
    kdeSelected = (id.comps.packages.has_key('kdebase')
                   and id.comps.packages['kdebase'].selected)

    if gnomeSelected:
        id.desktop.setDefaultDesktop("GNOME")
    elif kdeSelected:
        id.desktop.setDefaultDesktop("KDE")

    if gnomeSelected or kdeSelected:
        id.desktop.setDefaultRunLevel(5)


def checkDependencies(dir, intf, disp, id, instPath):
    if dir == dispatch.DISPATCH_BACK:
	return

    win = intf.waitWindow(_("Dependency Check"),
      _("Checking dependencies in packages selected for installation..."))

    id.dependencies = id.comps.verifyDeps(instPath, id.upgrade.get())

    win.pop()

    if id.dependencies:
	disp.skipStep("dependencies", skip = 0)
    else:
	disp.skipStep("dependencies")

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
	    self.instLog.write (self.modeText % (h[rpm.RPMTAG_NAME],))
	    self.instLog.flush ()
	    fn = self.method.getFilename(h, self.pkgTimer)

	    self.rpmFD = -1
	    while self.rpmFD < 0:
		try:
		    self.rpmFD = os.open(fn, os.O_RDONLY)
		    # Make sure this package seems valid
		    try:
			(h, isSource) = rpm.headerFromPackage(self.rpmFD)
			os.lseek(self.rpmFD, 0, 0)
		    except:
			self.rpmFD = -1
			os.close(self.rpmFD)
			raise SystemError
		except:
		    self.messageWindow(_("Error"),
			_("The file %s cannot be opened. This is due to "
			  "a missing file, a bad package, or bad media. "
			  "Press <return> to try again.") % fn)

	    fn = self.method.unlinkFilename(fn)
	    return self.rpmFD
	elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	    if total:
		self.progress.setPackageScale(amount, total)
	    pass
	elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
	    os.close (self.rpmFD)
	    self.progress.completePackage(h, self.pkgTimer)
	else:
	    pass

	self.progress.processEvents()

    def __init__(self, messageWindow, progress, pkgTimer, method,
		 progressWindowClass, instLog, modeText):
	self.messageWindow = messageWindow
	self.progress = progress
	self.pkgTimer = pkgTimer
	self.method = method
	self.progressWindowClass = progressWindowClass
	self.progressWindow = None
	self.instLog = instLog
	self.modeText = modeText

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
    elif string.lower(first[rpm.RPMTAG_NAME]) < string.lower(second[rpm.RPMTAG_NAME]):
	return -1
    elif string.lower(first[rpm.RPMTAG_NAME]) > string.lower(second[rpm.RPMTAG_NAME]):
	return 1

    return 0

class rpmErrorClass:

    def cb(self):
	self.f.write (rpm.errorString () + "\n")

    def __init__(self, f):
	self.f = f

def turnOnFilesystems(dir, fsset, diskset, upgrade, instPath):
    if dir == dispatch.DISPATCH_BACK:
	fsset.umountFilesystems(instPath)
	return

    if flags.setupFilesystems:
	if not upgrade.get():
	    diskset.savePartitions ()
            fsset.formatSwap(instPath)
            fsset.turnOnSwap(instPath)
	    fsset.makeFilesystems (instPath)
            fsset.mountFilesystems (instPath)

def doInstall(method, id, intf, instPath):
    if flags.test:
	return

    arch = iutil.getArch ()

    if arch == "alpha":
	# if were're on alpha with ARC console, set the clock
	# so that our installed files won't be in the future
        from milo import MiloInstall, onMILO
	if onMILO ():
	    args = ("clock", "-A", "-s")
	    try:
		iutil.execWithRedirect('/usr/sbin/clock', args)
	    except:
		pass

    # shorthand
    upgrade = id.upgrade.get()

    if not upgrade:
	# this is NICE and LATE. It lets kickstart/server/workstation
	# installs detect this properly
	if (id.hdList.has_key('kernel-smp') and isys.smpAvailable()):
	    id.hdList['kernel-smp'].selected = 1

	if (id.hdList.has_key('kernel-enterprise')):
	    import lilo

	    if lilo.needsEnterpriseKernel():
		id.hdList['kernel-enterprise'].selected = 1

	# we *always* need a kernel installed
	if (id.hdList.has_key('kernel')):
	    id.hdList['kernel'].selected = 1

	# if NIS is configured, install ypbind and dependencies:
	if id.auth.useNIS:
	    id.hdList['ypbind'].selected = 1
	    id.hdList['yp-tools'].selected = 1
	    id.hdList['portmap'].selected = 1

	if id.auth.useLdap:
	    id.hdList['nss_ldap'].selected = 1
	    id.hdList['openldap'].selected = 1
	    id.hdList['perl'].selected = 1

	if id.auth.useKrb5:
	    id.hdList['pam_krb5'].selected = 1
	    id.hdList['krb5-workstation'].selected = 1
	    id.hdList['krbafs'].selected = 1
	    id.hdList['krb5-libs'].selected = 1

        xserver = id.videocard.primaryCard().getXServer()
        if (xserver and id.comps.packages.has_key('XFree86')
            and id.comps.packages['XFree86'].selected
            and xserver != "XFree86"):
            try:
                id.hdList['XFree86-' + xserver[5:]].selected = 1
            except ValueError, message:
                log ("Error selecting XFree86 server package: %s", message)
                
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
	return 1

    for i in ( '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
	       '/etc/sysconfig', '/etc/sysconfig/network-scripts',
	       '/etc/X11' ):
	try:
	    os.mkdir(instPath + i)
	except os.error, (errno, msg):
	    # self.intf.messageWindow("Error", "Error making directory %s: %s" % (i, msg))
	    pass

    db = rpm.opendb(1, instPath)
    ts = rpm.TransactionSet(instPath, db)

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

    for p in l:
	ts.add(p.h, p.h, how)
	total = total + 1
	totalSize = totalSize + (p[rpm.RPMTAG_SIZE] / 1024 )

    if not id.hdList.preordered():
	log ("WARNING: not all packages in hdlist had order tag")
	ts.order()

    if upgrade:
	logname = '/tmp/upgrade.log'
    else:
	logname = '/tmp/install.log'

    instLogName = instPath + logname
    try:
	os.unlink (instLogName)
    except OSError:
	pass

    instLog = open(instLogName, "w+")
    syslog = iutil.InstSyslog (instPath, instPath + logname)

    ts.scriptFd = instLog.fileno ()
    # the transaction set dup()s the file descriptor and will close the
    # dup'd when we go out of scope

    if upgrade:
	modeText = _("Upgrading %s.\n")
    else:
	modeText = _("Installing %s.\n")

    errors = rpmErrorClass(instLog)
    oldError = rpm.errorSetCallback (errors.cb)
    pkgTimer = timer.Timer(start = 0)

    id.instProgress.setSizes(total, totalSize)
    id.instProgress.processEvents()

    cb = InstallCallback(intf.messageWindow, id.instProgress, pkgTimer,
			 method, intf.progressWindow, instLog, modeText)

    problems = ts.run(0, ~rpm.RPMPROB_FILTER_DISKSPACE, cb.cb, 0)

#        problems = ts.run(rpm.RPMTRANS_FLAG_TEST, ~0, self.instCallback, 0)

    if problems:
	spaceneeded = {}
	nodeneeded = {}
	size = 12

	# XXX
	nodeprob = -1
	if rpm.__dict__.has_key ("RPMPROB_DISKNODES"):
	    nodeprob = rpm.RPMPROB_DISKNODES

	for (descr, (type, mount, need)) in problems:
	    idx = string.find (mount, "/mnt/sysimage")
	    if mount[0:13] == "/mnt/sysimage":
		mount = mount[13:]
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
		log ("WARNING: unhandled problem returned from transaction set type %d",
		     type)

	probs = ""
	if spaceneeded:
	    probs = probs + _("You don't appear to have enough disk space to install "
			      "the packages you've selected. You need more space on the "
			      "following filesystems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"), _("Space Needed"))

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
	    probs = probs + _("You don't appear to have enough file nodes to install "
			      "the packages you've selected. You need more file nodes on the "
			      "following filesystems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"), _("Nodes Needed"))

	    for (mount, need) in nodeneeded.items ():
		prob = "%-15s %d\n" % (mount, need)
		probs = probs + prob

	intf.messageWindow (_("Disk Space"), probs)

	del ts
	del db
	instLog.close()
	del syslog

	method.systemUnmounted ()

	rpm.errorSetCallback (oldError)
	return dispatch.DISPATCH_BACK

    # This should close the RPM database so that you can
    # do RPM ops in the chroot in a %post ks script
    del ts
    del db
    rpm.errorSetCallback (oldError)
    
    method.filesDone ()
    
    del p

    if upgrade:
	instLog.write ("\n\nThe following packages were available on the CD but NOT upgraded:\n")
	for p in id.hdList.packages.values ():
	    if not p.selected:
		instLog.write("%s-%s-%s.%s.rpm\n" %
				   (p.h[rpm.RPMTAG_NAME],
				    p.h[rpm.RPMTAG_VERSION],
				    p.h[rpm.RPMTAG_RELEASE],
				    p.h[rpm.RPMTAG_ARCH]))
    instLog.close ()

    id.instProgress = None

    createWindow = (intf.progressWindow,
		    (_("Post Install"),
		     _("Performing post install configuration..."), 8))
    w = apply(apply, createWindow)

    try:
	if not upgrade:
	    # XXX
	    #if self.fdDevice[0:2] == "fd":
		#self.fstab.addMount(self.fdDevice, "/mnt/floppy", "auto")
	    #self.fstab.write (instPath)

	    w.set(1)

	    copyExtraModules(instPath, id.comps, id.extraModules)

	    w.set(2)

	    # pcmcia is supported only on i386 at the moment
	    if arch == "i386":
		pcmcia.createPcmciaConfig(
			instPath + "/etc/sysconfig/pcmcia")
		       
	    # rootpath mode doesn't have this file around
	    if os.access("/tmp/modules.conf", os.R_OK):
		iutil.copyFile("/tmp/modules.conf", 
			       instPath + "/etc/modules.conf")

	    # XXX
	    #if not self.x.skip and self.x.server:
		#if os.access (instPath + "/etc/X11/X", os.R_OK):
		    #os.rename (instPath + "/etc/X11/X",
			       #instPath + "/etc/X11/X.rpmsave")
		#try:
		    #os.unlink (instPath + "/etc/X11/X")
		#except OSError:
		    #pass
		#os.symlink ("../../usr/X11R6/bin/" + self.x.server,
			    #instPath + "/etc/X11/X")

		#self.x.write (instPath + "/etc/X11")

	    w.set(3)

	    # blah.  If we're on a serial mouse, and we have X, we need to
	    # close the mouse device, then run kudzu, then open it again.

	    # turn it off
	    mousedev = None

	    # XXX currently Bad Things (X async reply) happen when doing
	    # Mouse Magic on Sparc (Mach64, specificly)
	    if os.environ.has_key ("DISPLAY") and not arch == "sparc":
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

	    unmountUSB = 0
	    try:
		isys.mount('/usbdevfs', instPath+'/proc/bus/usb', 'usbdevfs')
		unmountUSB = 1
	    except:
		log("Mount of /proc/bus/usb failed")
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

	w.set(4)

	if upgrade:
	    # move the rebuilt db into place.
	    try:
		iutil.rmrf (instPath + "/var/lib/rpm.rpmsave")
	    except OSError:
		pass
	    os.rename (instPath + "/var/lib/rpm",
		       instPath + "/var/lib/rpm.rpmsave")
	    os.rename (instPath + self.dbpath,
		       instPath + "/var/lib/rpm")

	    # XXX - rpm 4.0.2 %post braindeadness support
	    try:
		os.unlink (instPath + "/etc/rpm/macros.db1")
	    except OSError:
		pass

	    # needed for prior systems which were not xinetd based
	    migrateXinetd(instPath, instLogName)

	if flags.setupFilesystems:
	    errors = None

	    if 0:
		if arch == "sparc":
		    errors = self.silo.install (self.fstab, instPath, 
					id.hdList, upgrade)
		elif arch == "i386":
		    defaultlang = self.language.getLangNickByName(self.language.getDefault())
		    langlist = expandLangs(defaultlang)
		    errors = self.lilo.install (self.fstab, instPath, 
					id.hdList, upgrade, langlist)
		elif arch == "ia64":
		    errors = self.eli.install (self.fstab, instPath, 
					id.hdList, upgrade)
		elif arch == "alpha":
		    errors = self.milo.write ()
		else:
		    raise RuntimeError, "What kind of machine is this, anyway?!"

	    if errors:
		w.pop()
		mess = _("An error occured while installing "
			 "the bootloader.\n\n"
			 "We HIGHLY recommend you make a recovery "
			 "boot floppy when prompted, otherwise you "
			 "may not be able to reboot into Red Hat Linux."
			 "\n\nThe error reported was:\n\n") + errors
		self.intf.messageWindow(_("Bootloader Errors"), mess)

		# make sure bootdisk window appears
		if iutil.getArch () == "i386":
		    self.instClass.removeFromSkipList('bootdisk')
		    self.bootdisk = 1

		w = apply(apply, createWindow)


	    w.set(5)

	    # go ahead and depmod modules as modprobe in rc.sysinit
	    # will complain loaduly if we don't do it now.
	    depmodModules(id.comps, instPath)

	w.set(6)

	id.instClass.postAction(instPath, flags.serial)

	w.set(7)

	if flags.setupFilesystems:
	    f = open("/tmp/cleanup", "w")
	    method.writeCleanupPath(f)
	    # XXX
	    #self.fstab.writeCleanupPath(f)
	    f.close()

	w.set(8)

	del syslog

    finally:
	pass

    w.pop ()

    sys.stdout.flush()

def migrateXinetd(self, instPath, instLog):
    if not os.access (instPath + "/usr/sbin/inetdconvert", os.X_OK):
	log("did not find %s" % instPath + "/usr/sbin/inetdconvert")
	return

    if not os.access (instPath + "/etc/inetd.conf.rpmsave", os.R_OK):
	log("did not run inetdconvert because no inetd.conf.rpmsave found")
	return

    argv = [ "/usr/sbin/inetdconvert", "--convertremaining",
	     "--inetdfile", "/etc/inetd.conf.rpmsave" ]
    
    log("found inetdconvert, executing %s" % argv)

    logfile = os.open (instLog, os.O_APPEND)
    iutil.execWithRedirect(argv[0], argv, root = instPath,
			   stdout = logfile, stderr = logfile)
    os.close(logfile)

def copyExtraModules(instPath, comps, extraModules):
    kernelVersions = comps.kernelVersionList()

    for (path, subdir, name, pkg) in extraModules:
	pattern = ""
	names = ""
	for (n, tag) in kernelVersions:
	    pattern = pattern + " " + n + "/" + name + ".o"
	    names = names + " " + name + ".o"
	command = ("cd %s/lib/modules; gunzip < %s/modules.cgz | " +
		    "%s/bin/cpio  --quiet -iumd %s") % \
	    (instPath, path, instPath, pattern)
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

def depmodModules(comps, instPath):
    kernelVersions = comps.kernelVersionList()

    for (version, tag) in kernelVersions:
	iutil.execWithRedirect ("/sbin/depmod",
				[ "/sbin/depmod", "-a", version ],
				root = instPath, stderr = '/dev/null')

