import os

from bootloaderInfo import *
import iutil

class s390BootloaderInfo(bootloaderInfo):
    def getBootloaderConfig(self, instRoot, bl, kernelList,
                            chainList, defaultDev):
        # on upgrade read in the lilo config file
        lilo = LiloConfigFile ()
        self.perms = 0600
        confFile = instRoot + self.configfile

        if os.access (confFile, os.R_OK):
            self.perms = os.stat(confFile)[0] & 0777
            lilo.read(confFile)
            os.rename(confFile, confFile + ".rpmsave")

        # Remove any invalid entries that are in the file; we probably
        # just removed those kernels. 
        for label in lilo.listImages():
            (fsType, sl, path, other) = lilo.getImage(label)
            if fsType == "other": continue

            if not os.access(instRoot + sl.getPath(), os.R_OK):
                lilo.delImage(label)

        rootDev = self.storage.rootDevice

        if rootDev.name == defaultDev.name:
            lilo.addEntry("default", kernelList[0][0])
        else:
            lilo.addEntry("default", chainList[0][0])

        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = self.kernelLocation + "vmlinuz" + kernelTag

            try:
                lilo.delImage(label)
            except IndexError, msg:
                pass

            sl = LiloConfigFile(imageType = "image", path = kernelFile)

            initrd = self.makeInitrd(kernelTag, instRoot)

            sl.addEntry("label", label)
            if initrd:
                sl.addEntry("initrd", "%s%s" %(self.kernelLocation, initrd))

            sl.addEntry("read-only")
            sl.addEntry("root", rootDev.path)
            sl.addEntry("ipldevice", rootDev.path[:-1])

            if self.args.get():
                sl.addEntry('append', '"%s"' % self.args.get())
                
            lilo.addImage (sl)

        for (label, longlabel, device) in chainList:
            if ((not label) or (label == "")):
                continue
            try:
                (fsType, sl, path, other) = lilo.getImage(label)
                lilo.delImage(label)
            except IndexError:
                sl = LiloConfigFile(imageType = "other",
                                    path = "/dev/%s" %(device))
                sl.addEntry("optional")

            sl.addEntry("label", label)
            lilo.addImage (sl)

        # Sanity check #1. There could be aliases in sections which conflict
        # with the new images we just created. If so, erase those aliases
        imageNames = {}
        for label in lilo.listImages():
            imageNames[label] = 1

        for label in lilo.listImages():
            (fsType, sl, path, other) = lilo.getImage(label)
            if sl.testEntry('alias'):
                alias = sl.getEntry('alias')
                if imageNames.has_key(alias):
                    sl.delEntry('alias')
                imageNames[alias] = 1

        # Sanity check #2. If single-key is turned on, go through all of
        # the image names (including aliases) (we just built the list) and
        # see if single-key will still work.
        if lilo.testEntry('single-key'):
            singleKeys = {}
            turnOff = 0
            for label in imageNames.keys():
                l = label[0]
                if singleKeys.has_key(l):
                    turnOff = 1
                singleKeys[l] = 1
            if turnOff:
                lilo.delEntry('single-key')

        return lilo

    def writeChandevConf(self, bl, instroot):   # S/390 only 
        cf = "/etc/chandev.conf"
        self.perms = 0644
        if bl.args.chandevget():
            fd = os.open(instroot + "/etc/chandev.conf",
                         os.O_WRONLY | os.O_CREAT)
            os.write(fd, "noauto\n")
            for cdev in bl.args.chandevget():
                os.write(fd,'%s\n' % cdev)
            os.close(fd)
        return ""
        
    
    def writeZipl(self, instRoot, bl, kernelList, chainList,
                  defaultDev, justConfigFile):
        rootDev = self.storage.rootDevice
        
        cf = '/etc/zipl.conf'
        self.perms = 0600
        if os.access (instRoot + cf, os.R_OK):
            self.perms = os.stat(instRoot + cf)[0] & 0777
            os.rename(instRoot + cf,
                      instRoot + cf + '.rpmsave')

        f = open(instRoot + cf, "w+")        

        f.write('[defaultboot]\n')
        f.write('default=' + kernelList[0][0] + '\n')
        f.write('target=%s\n' % (self.kernelLocation))

        cfPath = "/boot/"
        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

            initrd = self.makeInitrd(kernelTag, instRoot)
            f.write('[%s]\n' % (label))
            f.write('\timage=%s\n' % (kernelFile))
            if initrd:
                f.write('\tramdisk=%s%s\n' %(self.kernelLocation, initrd))

            realroot = rootDev.fstabSpec
            f.write('\tparameters="root=%s' %(realroot,))
            if bl.args.get():
                f.write(' %s' % (bl.args.get()))
            f.write('"\n')

        f.close()

        if not justConfigFile:
            rc = iutil.execWithRedirect("/sbin/zipl", [], root = instRoot,
                                        stdout = "/dev/stdout",
                                        stderr = "/dev/stderr")
            if rc:
                return rc

        return 0

    def write(self, instRoot, bl, kernelList, chainList,
            defaultDev):
        rc = self.writeZipl(instRoot, bl, kernelList, 
                            chainList, defaultDev,
                            not self.useZiplVal)
        if rc:
            return rc

        return self.writeChandevConf(bl, instRoot)

    def __init__(self, anaconda):
        bootloaderInfo.__init__(self, anaconda)
        self.useZiplVal = 1      # only used on s390
        self.kernelLocation = "/boot/"
        self._configdir = "/etc"
        self._configname = "zipl.conf"
