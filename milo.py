from lilo import LiloConfiguration
import iutil
import isys
import string
import os
import rpm

def onMILO ():
    try:
        f = open ('/proc/cpuinfo', 'r')
    except:
        return
    lines = f.readlines ()
    serial = ""
    for line in lines:
        if string.find (line, "system serial number") >= 0:
            serial = string.strip (string.split (line, ':')[1])

    if serial and len (serial) >= 4 and serial[0:4] == "MILO":
        return 1
    else:
        return 0

def partitionNum (path):
    i = len(path) - 1
    while path[i] in string.digits:
        i = i - 1
    return string.atoi (path[i + 1:])

def wholeDevice (path):
    i = len(path) - 1
    while path[i] in string.digits:
        i = i - 1
    extra = 1
    if string.find(path, "rd/") >= 0:
        extra = 0
    return path[:i + extra]

class MiloInstall:
    def __init__ (self, todo):
	self.initrdsMade = {}
        self.todo = todo

    def makeInitrd (self, kernelTag, instRoot):
	initrd = "initrd%s.img" % (kernelTag, )
	if not self.initrdsMade.has_key(initrd):
            iutil.execWithRedirect("/sbin/mkinitrd",
                                   ("/sbin/mkinitrd",
				    "--ifneeded",
                                    "/boot/" + initrd,
                                    kernelTag[1:]),
                                  stdout = None, stderr = None, searchPath = 1,
                                  root = instRoot)
	    self.initrdsMade[kernelTag] = 1
	return initrd

    def writeAboot (self):
        bootDevice = self.todo.fstab.getBootDevice ()
        rootDevice = self.todo.fstab.getRootDevice ()[0]
        if bootDevice != rootDevice:
            confprefix = self.todo.instPath + "/boot/etc"
            kernelprefix = '/'
            try:
                os.mkdir (confprefix)
            except:
		pass
            # XXX stat /etc/aboot.conf and do the right thing
            try:
		os.remove(self.todo.instPath + "/etc/aboot.conf")
            except OSError:
                pass
            os.symlink("../boot/etc/aboot.conf",
                       self.todo.instPath + "/etc/aboot.conf")

        else:
            confprefix = self.todo.instPath + "/etc"
            kernelprefix = '/boot/'
            
        partition = partitionNum (bootDevice)
        abootdev = wholeDevice (bootDevice)

        if os.access (confprefix + "/aboot.conf", os.R_OK):
            os.rename (confprefix + "/aboot.conf",
                       confprefix + "/aboot.conf.rpmsave")
        f = open (confprefix + "/aboot.conf", 'w')
        f.write ("# aboot default configurations\n")
        if bootDevice != rootDevice:
            f.write ("# NOTICE:  You have a /boot partition.  This means that\n")
            f.write ("#          all kernel paths are relative to /boot/\n")

        lines = 0
        kernelList = []
        hdList = self.todo.hdList
        upgrade = self.todo.upgrade
	smpInstalled = (hdList.has_key('kernel-smp') and 
                        hdList['kernel-smp'].selected)

	# This is a bit odd, but old versions of Red Hat could install
	# SMP kernels on UP systems, but (properly) configure the UP version.
	# We don't want to undo that, but we do want folks using this install
	# to be able to override the kernel to use during installs. This rule
	# seems to nail this.
	if (upgrade and not isys.smpAvailable()):
	    smpInstalled = 0

	if (isys.smpAvailable() and hdList.has_key('kernel-enterprise') and 
            hdList['kernel-enterprise'].selected):
	    kernelList.append((hdList['kernel-enterprise'], "enterprise"))

	if (smpInstalled):
	    kernelList.append((hdList['kernel-smp'], "smp"))

	kernelList.append((hdList['kernel'], ""))
        
	for (kernel, tag) in kernelList:
	    kernelTag = "-%s-%s%s" % (kernel[rpm.RPMTAG_VERSION],
                                      kernel[rpm.RPMTAG_RELEASE], tag)
	    kernelFile = "vmlinuz" + kernelTag
            initrd = self.makeInitrd (kernelTag, self.todo.instPath)
            extra=""
            if os.access (self.todo.instPath + "/boot/" + initrd, os.R_OK):
                extra=" initrd=%s%s" % (kernelprefix, initrd)
            f.write ("%d:%d%s%s root=/dev/%s%s\n" %
                     (lines, partition, kernelprefix,
                      kernelFile, rootDevice, extra))
            lines = lines + 1

        f.close ()

        args = ("swriteboot", ("/dev/%s" % abootdev), "/boot/bootlx")
        iutil.execWithRedirect('/sbin/swriteboot',
                               args,
                               stdout = None,
                               root = self.todo.instPath)
        
        args = ("abootconf", ("/dev/%s" % abootdev), str (partition))
        iutil.execWithRedirect('/sbin/abootconf',
                               args,
                               stdout = None,
                               root = self.todo.instPath)
    def writeMilo (self):
        bootDevice = self.todo.fstab.getBootDevice ()
        rootDevice = self.todo.fstab.getRootDevice ()[0]
        
        if bootDevice != rootDevice:
            hasboot = 1
            kernelroot = '/'
            try:
		os.remove(self.todo.instPath + "/etc/milo.conf")
            except OSError:
		pass
            os.symlink("../boot/milo.conf",
                       self.todo.instPath + "/etc/milo.conf")
            if os.access (self.todo.instPath + "/boot/milo.conf", os.R_OK):
                os.rename (self.todo.instPath + "/boot/milo.conf",
                           self.todo.instPath + "/boot/milo.conf.rpmsave")
        else:
            hasboot = 0
            kernelroot = '/boot/'
            if os.access (self.todo.instPath + "/etc/milo.conf", os.R_OK):
                os.rename (self.todo.instPath + "/etc/milo.conf",
                           self.todo.instPath + "/etc/milo.conf.rpmsave")

        f = open (self.todo.instPath + "/etc/milo.conf", "w")
        if hasboot:
            f.write ("# NOTICE:  You have a /boot partition.  This means that all\n")
            f.write ("#          paths are relative to /boot/\n")

        kernels = []
        for package, tag in (('kernel-smp', 'smp'), ('kernel', '')):
            if (self.todo.hdList.has_key(package) and
                self.todo.hdList[package].selected):
                kernel = self.todo.hdList[package]
                version = "%s-%s" % (kernel[rpm.RPMTAG_VERSION],
                                     kernel[rpm.RPMTAG_RELEASE])
                # if this is UP and we have a kernel (the smp kernel),
                # then call it linux-up
                if not tag and kernels:
                    kernels.append ((version, "linux-up"))
                else:
                    kernels.append ((version, "linux"))
        for version, label in kernels:
            f.write ("image=%svmlinuz-%s\n" % (kernelroot, version))
            f.write ("\tlabel=%s\n" % label)
            f.write ("\troot=/dev/%s\n" % rootDevice)
        f.close()
                
    def write (self):
        if onMILO ():
            self.writeMilo ()
        else:
            self.writeAboot ()

        
    
