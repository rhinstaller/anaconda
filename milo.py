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
    i = 0
    while path[i] not in string.digits:
        i = i + 1
    return string.atoi (path[i:])

def wholeDevice (path):
    i = 0
    while path[i] not in string.digits:
        i = i + 1
    return path[:i]

class MiloInstall:
    def __init__ (self, todo):
	self.initrdsMade = {}
        self.todo = todo

    def makeInitrd (self, kernelTag, instRoot):
	initrd = "/boot/initrd%s.img" % (kernelTag, )
	if not self.initrdsMade.has_key(initrd):
            iutil.execWithRedirect("/sbin/mkinitrd",
                                  [ "/sbin/mkinitrd",
				    "--ifneeded",
                                    initrd,
                                    kernelTag[1:] ],
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
        for package, tag in (('kernel-smp', 'smp'), ('kernel', '')):
            if (self.todo.hdList.has_key(package) and
                self.todo.hdList[package].selected):
                kernel = self.todo.hdList[package]
                initrd = self.makeInitrd (tag, self.todo.instPath)
                extra=""
                if os.access (self.todo.instPath + initrd, os.R_OK):
                    extra=" initrd=%s/%s" % (kernelprefix, initrd)
                version = "%s-%s" % (kernel[rpm.RPMTAG_VERSION],
                                     kernel[rpm.RPMTAG_RELEASE])
                f.write ("%d:%d%svmlinuz-%s%s root=/dev/%s%s\n" %
                         (lines, partition, kernelprefix,
                          version, tag, rootDevice, extra))
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

        
    
