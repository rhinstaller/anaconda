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

import iutil
import isys
import rpm
import os
import timer
import time
import sys
import string
import pcmcia
import fsset
from log import log
from flags import flags
from constants import *
from translate import _
from syslogd import syslog

rpm.addMacro("_i18ndomains", "redhat-dist")

def queryUpgradeContinue(intf, dir):
    if dir == DISPATCH_FORWARD:
        return

    rc = intf.messageWindow(_("Proceed with upgrade?"),
                       _("The filesystems of the Linux installation "
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
    if dir == DISPATCH_BACK:
	return

    win = intf.waitWindow(_("Dependency Check"),
      _("Checking dependencies in packages selected for installation..."))

    id.dependencies = id.comps.verifyDeps(instPath, id.upgrade.get())

    win.pop()

    if id.dependencies and id.comps.canResolveDeps(id.dependencies):
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
	    self.progress.processEvents()
	else:
	    pass

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
    

def turnOnFilesystems(dir, thefsset, diskset, upgrade, instPath):
    if dir == DISPATCH_BACK:
	thefsset.umountFilesystems(instPath)
	return

    if flags.setupFilesystems:
	if not upgrade.get():
            thefsset.setActive(diskset)
            if not thefsset.isActive():
                diskset.savePartitions ()
            thefsset.checkBadblocks(instPath)
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

    def select(hdList, name):
        if hdList.has_key(name):
            hdList[name].selected = 1

    if not upgrade:
	# this is NICE and LATE. It lets kickstart/server/workstation
	# installs detect this properly
	if arch == "s390" or arch == "s390x":
	    if (string.find(os.uname()[2], "tape") > -1):
		select(id.hdList, 'kernel-tape')
	    else:
		select(id.hdList, 'kernel')
	elif isys.smpAvailable():
            select(id.hdList, 'kernel-smp')

	if (id.hdList.has_key('kernel-enterprise')):
	    import lilo

	    if lilo.needsEnterpriseKernel():
		id.hdList['kernel-enterprise'].selected = 1

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

        if pcmcia.pcicType():
            select(id.hdList, 'kernel-pcmcia-cs')

        if iutil.getArch() != "s390" and iutil.getArch() != "s390x":
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
	       '/etc/X11' ):
	try:
	    os.mkdir(instPath + i)
	except os.error, (errno, msg):
            #self.intf.messageWindow("Error",
            #                        "Error making directory %s: "
            #                        "%s" % (i, msg))
	    pass

    # write out the fstab
    if not upgrade:
        id.fsset.write(instPath)
        # rootpath mode doesn't have this file around
        if os.access("/tmp/modules.conf", os.R_OK):
            iutil.copyFile("/tmp/modules.conf", 
                           instPath + "/etc/modules.conf")
#    delay writing migrate adjusted fstab till later, in case
#    rpm transaction set determines they don't have enough space to upgrade
#    else:
#        id.fsset.migratewrite(instPath)        


def doInstall(method, id, intf, instPath):
    if flags.test:
	return

    upgrade = id.upgrade.get()
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

    progress = intf.progressWindow(_("Processing"),
                                   _("Setting up RPM transaction..."),
                                   len(l))

    i = 0
    for p in l:
	ts.add(p.h, p.h, how)
	total = total + 1
	totalSize = totalSize + (p[rpm.RPMTAG_SIZE] / 1024)
        i = i + 1
        progress.set(i)

    progress.pop()
    
    if not id.hdList.preordered():
	log ("WARNING: not all packages in hdlist had order tag")
	ts.order()

    if upgrade:
	logname = '/tmp/upgrade.log'
    else:
	logname = '/tmp/install.log'

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

    # write out migrate adjusted fstab so kernel RPM can get initrd right
    if upgrade:
        id.fsset.migratewrite(instPath)
    if id.upgradeDeps:
        instLog.write(_("\n\nThe following packages were automatically\n"
                        "selected to be installed:"
                        "\n"
                        "%s"
                        "\n\n") % (id.upgradeDeps,))
        

    problems = ts.run(0, ~rpm.RPMPROB_FILTER_DISKSPACE, cb.cb, 0)

    # force test mode install
    # problems = ts.run(rpm.RPMTRANS_FLAG_TEST, ~0, self.instCallback, 0)

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
		log ("WARNING: unhandled problem returned from "
                     "transaction set type %d",
		     type)

	probs = ""
	if spaceneeded:
	    probs = probs + _("You don't appear to have enough disk space "
                              "to install the packages you've selected. "
                              "You need more space on the following "
                              "filesystems:\n\n")
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
                              "filesystems:\n\n")
	    probs = probs + ("%-15s %s\n") % (_("Mount Point"),
                                              _("Nodes Needed"))

	    for (mount, need) in nodeneeded.items ():
		prob = "%-15s %d\n" % (mount, need)
		probs = probs + prob

	intf.messageWindow (_("Disk Space"), probs)

	del ts
	del db
	instLog.close()

        syslog.stop()

	method.systemUnmounted ()

	rpm.errorSetCallback (oldError)
	return DISPATCH_BACK

    # This should close the RPM database so that you can
    # do RPM ops in the chroot in a %post ks script
    del ts
    del db
    rpm.errorSetCallback (oldError)
    
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

    arch = iutil.getArch ()
    if ( arch == "s390" or arch == "s390x"):
        syslog.stop()

    id.instProgress = None

def doPostInstall(method, id, intf, instPath):
    if flags.test:
	return
    
    w = intf.progressWindow(_("Post Install"),
                            _("Performing post install configuration..."), 7)

    upgrade = id.upgrade.get()
    arch = iutil.getArch ()

    if upgrade:
	logname = '/tmp/upgrade.log'
    else:
	logname = '/tmp/install.log'

    instLogName = instPath + logname
    instLog = open(instLogName, "a")
    
    try:
	if not upgrade:
	    w.set(1)

	    copyExtraModules(instPath, id.comps, id.extraModules)
            if iutil.getArch() == "s390" or iutil.getArch() == "s390x":
                copyOCOModules(instPath)
                
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
	    if os.environ.has_key ("DISPLAY") and not (arch == "sparc" or arch == "s390" or arch == "s390x"):
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

	    if arch != "s390" and arch != "s390x":
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
	    else:
		if os.access(instPath + '/etc/securetty', os.R_OK):
			securetty = open(instPath + '/etc/securetty','a')
			securetty.write("console\n")
			securetty.close()

	w.set(4)

	if upgrade:
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

	    # needed for prior systems which were not xinetd based
	    migrateXinetd(instPath, instLogName)

        w.set(5)

	if flags.setupFilesystems:
	    # go ahead and depmod modules as modprobe in rc.sysinit
	    # will complain loaduly if we don't do it now.
	    depmodModules(id.comps, instPath)

	w.set(6)

	if flags.setupFilesystems:
	    f = open("/tmp/cleanup", "w")
	    method.writeCleanupPath(f)
	    f.close()

	w.set(7)

    finally:
	pass

    w.pop ()

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

def copyOCOModules(instPath):
    command = ("[ -d /OCO ] && cp -a /OCO/* %s/lib/modules" % (instPath))
    log("running: '%s'" % (command, ))
    os.system(command)


def copyExtraModules(instPath, comps, extraModules):
    kernelVersions = comps.kernelVersionList()

    for (path, subdir, name) in extraModules:
	pattern = ""
	names = ""
	for (n, tag) in kernelVersions:
	    pattern = pattern + " " + n + "/" + name + ".o"
	    names = names + " " + name + ".o"
	command = ("cd %s/lib/modules; gunzip < %s/modules.cgz | "
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

def depmodModules(comps, instPath):
    kernelVersions = comps.kernelVersionList()

    for (version, tag) in kernelVersions:
	iutil.execWithRedirect ("/sbin/depmod",
				[ "/sbin/depmod", "-a", version, "-F", "/boot/System.map-" + version ],
				root = instPath, stderr = '/dev/null')

