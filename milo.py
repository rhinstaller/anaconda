from lilo import LiloConfiguration
import iutil
import isys
import string

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
        self.todo = todo

    def writeAboot (self):
        if self.todo.mounts.has_key ('/boot'):
            confprefix = self.todo.instPath + "/boot/etc"
            kernelprefix = '/'
            partition = partitionNum (self.todo.mounts['/boot'])
            abootdev = wholeDevice (self.todo.mounts['/boot'])
            try:
                os.mkdir (confprefix)
		os.remove(todo.instPath + "/etc/aboot.conf")
                os.symlink("../boot/etc/aboot.conf",
                           self.todo.instPath + "/etc/aboot.conf")
            except:
		pass
        else:
            confprefix = self.todo.instPath + "/etc"
            kernelprefix = '/boot/'
            partition = partitionNum (self.todo.mounts['/'])
            abootdev = wholeDevice (self.todo.mounts['/'])

        if os.access (confprefix + "/etc/aboot.conf", os.R_OK):
            os.rename (confprefix + "/etc/aboot.conf",
                       confprefix + "/etc/aboot.conf.rpmsave")
        f = open (confprefix + "/etc/aboot.conf", 'w')
        f.write ("# aboot default configurations\n")
        if self.todo.mounts.has_key ('/boot'):
            f.write ("# NOTICE:  You have a /boot partition.  This means that\n")
            f.write ("#          all kernel paths are relative to /boot/\n")

        lines = 0
        rootdev = self.todo.mounts['/']
        for package, tag in (('kernel-smp', 'smp'), ('kernel', '')):
            if (self.todo.hdList.has_key(package) and
                self.todo.hdList[package].selected):
                kernel = self.todo.hdList[package]
                version = "%s-%s" % (kernel['version'], kernel['release'])
                f.write ("%d:%d%svmlinuz-%s%s root=/dev/%s\n" %
                         (lines, partition, kernelprefix, version, tag, rootdev))
                lines = lines + 1

        f.close ()

        args = ("swriteboot", ("/dev/%s" % abootdev), "/boot/bootlx")
        iutil.execWithRedirect('/sbin/swriteboot',
                               args,
                               stdout = None,
                               root = todo.instPath)
        
        args = ("abootconf", ("/dev/%s" % abootdev), str (partition))
        iutil.execWithRedirect('/sbin/abootconf',
                               args,
                               stdout = None,
                               root = todo.instPath)
    def writeMilo (self):
        if self.todo.mounts.has_key ('/boot'):
            hasboot = 1
            kernelroot = '/'
            try:
		os.remove(todo.instPath + "/etc/milo.conf")
                os.symlink("../boot/milo.conf",
                           self.todo.instPath + "/etc/milo.conf")
            except:
		pass
        else:
            hasboot = 0
            kernelroot = '/boot/'

        f = open (self.todo.instPath + "/etc/milo.conf")
        if hasboot:
            f.write ("# NOTICE:  You have a /boot partition.  This means that all\n")
            f.write ("#          paths are relative to /boot/\n")

        kernels = []
        for package, tag in (('kernel-smp', 'smp'), ('kernel', '')):
            if (self.todo.hdList.has_key(package) and
                self.todo.hdList[package].selected):
                kernel = self.todo.hdList[package]
                version = "%s-%s" % (kernel['version'], kernel['release'])
                # if this is UP and we have a kernel (the smp kernel),
                # then call it linux-up
                if not tag and kernels:
                    kernels.append ((version, "linux-up"))
                else:
                    kernels.append ((version, "linux"))
        for version, label in kernels:
            f.write ("image=%svmlinuz-%s\n" % (kernelroot, version))
            f.write ("\tlabel=%s\n" % label)
            f.write ("\troot=/dev/%s" % self.todo.mounts ['/'])
                
    def write (self):
        if onMILO ():
            self.writeMilo ()
        else:
            self.writeAboot ()

        
    
