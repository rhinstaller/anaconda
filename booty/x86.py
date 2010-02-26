import os
import string

from booty import BootyNoKernelWarning
from util import getDiskPart
from bootloaderInfo import *
from flags import flags
import checkbootloader
import iutil

class x86BootloaderInfo(efiBootloaderInfo):
    def setPassword(self, val, isCrypted = 1):
        if not val:
            self.password = val
            self.pure = val
            return
        
        if isCrypted and self.useGrubVal == 0:
            self.pure = None
            return
        elif isCrypted:
            self.password = val
            self.pure = None
        else:
            salt = "$1$"
            saltLen = 8

            saltchars = string.letters + string.digits + './'
            for i in range(saltLen):
                salt += random.choice(saltchars)

            self.password = crypt.crypt(val, salt)
            self.pure = val
        
    def getPassword (self):
        return self.pure

    def setUseGrub(self, val):
        self.useGrubVal = val

    def getPhysicalDevices(self, device):
        # This finds a list of devices on which the given device name resides.
        # Accepted values for "device" are raid1 md devices (i.e. "md0"),
        # physical disks ("hda"), and real partitions on physical disks
        # ("hda1").  Volume groups/logical volumes are not accepted.
        dev = self.storage.devicetree.getDeviceByName(device)
        path = dev.path[5:]

        if device in map (lambda x: x.name, self.storage.lvs + self.storage.vgs):
            return []

        if path.startswith("mapper/luks-"):
            return []

        if dev.type == "mdarray":
            bootable = 0
            parts = checkbootloader.getRaidDisks(device, self.storage,
                                             raidLevel=1, stripPart=0)
            parts.sort()
            return parts

        return [device]

    def runGrubInstall(self, instRoot, bootDev, cmds, cfPath):
        if cfPath == "/":
            syncDataToDisk(bootDev, "/boot", instRoot)
        else:
            syncDataToDisk(bootDev, "/", instRoot)

        # copy the stage files over into /boot
        rc = iutil.execWithRedirect("/sbin/grub-install",
                                    ["--just-copy"],
                                    stdout = "/dev/tty5", stderr = "/dev/tty5",
                                    root = instRoot)
        if rc:
            return rc

        # really install the bootloader
        for cmd in cmds:
            p = os.pipe()
            os.write(p[1], cmd + '\n')
            os.close(p[1])

            # FIXME: hack to try to make sure everything is written
            #        to the disk
            if cfPath == "/":
                syncDataToDisk(bootDev, "/boot", instRoot)
            else:
                syncDataToDisk(bootDev, "/", instRoot)

            rc = iutil.execWithRedirect('/sbin/grub' ,
                                        [ "--batch", "--no-floppy",
                                          "--device-map=/boot/grub/device.map" ],
                                        stdin = p[0],
                                        stdout = "/dev/tty5", stderr = "/dev/tty5",
                                        root = instRoot)
            os.close(p[0])

            if rc:
                return rc

    def matchingBootTargets(self, stage1Devs, bootDevs):
        matches = []
        for stage1Dev in stage1Devs:
            for mdBootPart in bootDevs:
                if getDiskPart(stage1Dev, self.storage)[0] == getDiskPart(mdBootPart, self.storage)[0]:
                    matches.append((stage1Dev, mdBootPart))
        return matches

    def addMemberMbrs(self, matches, bootDevs):
        updatedMatches = list(matches)
        bootDevsHavingStage1Dev = [match[1] for match in matches]
        for mdBootPart in bootDevs:
            if mdBootPart not in bootDevsHavingStage1Dev:
               updatedMatches.append((getDiskPart(mdBootPart, self.storage)[0], mdBootPart))
        return updatedMatches

    def installGrub(self, instRoot, bootDev, grubTarget, grubPath, cfPath):
        if iutil.isEfi():
            return efiBootloaderInfo.installGrub(self, instRoot, bootDev, grubTarget,
                                                 grubPath, cfPath)

        args = "--stage2=/boot/grub/stage2 "

        stage1Devs = self.getPhysicalDevices(grubTarget)
        bootDevs = self.getPhysicalDevices(bootDev.name)

        installs = [(None,
                     self.grubbyPartitionName(stage1Devs[0]),
                     self.grubbyPartitionName(bootDevs[0]))]

        if bootDev.type == "mdarray":

            matches = self.matchingBootTargets(stage1Devs, bootDevs)

            # If the stage1 target disk contains member of boot raid array (mbr
            # case) or stage1 target partition is member of boot raid array
            # (partition case)
            if matches:
                # 1) install stage1 on target disk/partiton
                stage1Dev, mdMemberBootPart = matches[0]
                installs = [(None,
                             self.grubbyPartitionName(stage1Dev),
                             self.grubbyPartitionName(mdMemberBootPart))]
                firstMdMemberDiskGrubbyName = self.grubbyDiskName(getDiskPart(mdMemberBootPart, self.storage)[0])

                # 2) and install stage1 on other members' disks/partitions too
                # NOTES:
                # - the goal is to be able to boot after a members' disk removal
                # - so we have to use grub device names as if after removal
                #   (i.e. the same disk name (e.g. (hd0)) for both member disks)
                # - if member partitions have different numbers only removal of
                #   specific one of members will work because stage2 containing
                #   reference to config file is shared and therefore can contain
                #   only one value

                # if target is mbr, we want to install also to mbr of other
                # members, so extend the matching list
                matches = self.addMemberMbrs(matches, bootDevs)
                for stage1Target, mdMemberBootPart in matches[1:]:
                    # prepare special device mapping corresponding to member removal
                    mdMemberBootDisk = getDiskPart(mdMemberBootPart, self.storage)[0]
                    # It can happen due to ks --driveorder option, but is it ok?
                    if not mdMemberBootDisk in self.drivelist:
                        continue
                    mdRaidDeviceRemap = (firstMdMemberDiskGrubbyName,
                                         mdMemberBootDisk)

                    stage1TargetGrubbyName = self.grubbyPartitionName(stage1Target)
                    rootPartGrubbyName = self.grubbyPartitionName(mdMemberBootPart)

                    # now replace grub disk name part according to special device
                    # mapping
                    old = self.grubbyDiskName(mdMemberBootDisk).strip('() ')
                    new = firstMdMemberDiskGrubbyName.strip('() ')
                    rootPartGrubbyName = rootPartGrubbyName.replace(old, new)
                    stage1TargetGrubbyName = stage1TargetGrubbyName.replace(old, new)

                    installs.append((mdRaidDeviceRemap,
                                     stage1TargetGrubbyName,
                                     rootPartGrubbyName))

                # This is needed for case when /boot member partitions have
                # different numbers. Shared stage2 can contain only one reference
                # to grub.conf file, so let's ensure that it is reference to partition
                # on disk which we will boot from - that is, install grub to
                # this disk as last so that its reference is not overwritten.
                installs.reverse()

        cmds = []
        for mdRaidDeviceRemap, stage1Target, rootPart in installs:
            if mdRaidDeviceRemap:
                cmd = "device (%s) /dev/%s\n" % tuple(mdRaidDeviceRemap)
            else:
                cmd = ''
            cmd += "root %s\n" % (rootPart,)
            cmd += "install %s%s/stage1 d %s %s/stage2 p %s%s/grub.conf" % \
                (args, grubPath, stage1Target, grubPath, rootPart, grubPath)
            cmds.append(cmd)
        return self.runGrubInstall(instRoot, bootDev.name, cmds, cfPath)

    def writeGrub(self, instRoot, bl, kernelList, chainList,
            defaultDev, upgrade=False):

        rootDev = self.storage.rootDevice
        grubTarget = bl.getDevice()

        try:
            bootDev = self.storage.mountpoints["/boot"]
            grubPath = "/grub"
            cfPath = "/"
        except KeyError:
            bootDev = rootDev
            grubPath = "/boot/grub"
            cfPath = "/boot/"

        if not upgrade:
            self.writeGrubConf(instRoot, bootDev, rootDev, defaultDev, kernelList,
                               chainList, grubTarget, grubPath, cfPath)

        # keep track of which devices are used for the device.map
        usedDevs = set()
        usedDevs.update(self.getPhysicalDevices(grubTarget))
        usedDevs.update(self.getPhysicalDevices(rootDev.name))
        usedDevs.update(self.getPhysicalDevices(bootDev.name))
        usedDevs.update([dev for (label, longlabel, dev) in chainList if longlabel])

        if not upgrade:
            self.writeDeviceMap(instRoot, usedDevs, upgrade)
            self.writeSysconfig(instRoot, grubTarget, upgrade)

        return self.installGrub(instRoot, bootDev, grubTarget, grubPath, cfPath)

    def writeGrubConf(self, instRoot, bootDev, rootDev, defaultDev, kernelList,
                      chainList, grubTarget, grubPath, cfPath):

        bootDevs = self.getPhysicalDevices(bootDev.name)

        # XXX old config file should be read here for upgrade

        cf = "%s%s" % (instRoot, self.configfile)
        self.perms = 0600
        if os.access (cf, os.R_OK):
            self.perms = os.stat(cf)[0] & 0777
            os.rename(cf, cf + '.rpmsave')

        f = open(cf, "w+")

        f.write("# grub.conf generated by anaconda\n")
        f.write("#\n")
        f.write("# Note that you do not have to rerun grub "
                "after making changes to this file\n")

        if grubPath == "/grub":
            f.write("# NOTICE:  You have a /boot partition.  This means "
                    "that\n")
            f.write("#          all kernel and initrd paths are relative "
                    "to /boot/, eg.\n")
        else:
            f.write("# NOTICE:  You do not have a /boot partition.  "
                    "This means that\n")
            f.write("#          all kernel and initrd paths are relative "
                    "to /, eg.\n")            
        
        f.write('#          root %s\n' % self.grubbyPartitionName(bootDevs[0]))
        f.write("#          kernel %svmlinuz-version ro root=%s\n" % (cfPath, rootDev.path))
        f.write("#          initrd %sinitrd-[generic-]version.img\n" % (cfPath))
        f.write("#boot=/dev/%s\n" % (grubTarget))

        # get the default image to boot... we have to walk and find it
        # since grub indexes by where it is in the config file
        if defaultDev.name == rootDev.name:
            default = 0
        else:
            # if the default isn't linux, it's the first thing in the
            # chain list
            default = len(kernelList)


        f.write('default=%s\n' % (default))
        f.write('timeout=%d\n' % (self.timeout or 0))

        if self.serial == 1:
            # grub the 0-based number of the serial console device
            unit = self.serialDevice[-1]
            
            # and we want to set the speed too
            speedend = 0
            for char in self.serialOptions:
                if char not in string.digits:
                    break
                speedend = speedend + 1
            if speedend != 0:
                speed = self.serialOptions[:speedend]
            else:
                # reasonable default
                speed = "9600"
                
            f.write("serial --unit=%s --speed=%s\n" %(unit, speed))
            f.write("terminal --timeout=%s serial console\n" % (self.timeout or 5))
        else:
            # we only want splashimage if they're not using a serial console
            if os.access("%s/boot/grub/splash.xpm.gz" %(instRoot,), os.R_OK):
                f.write('splashimage=%s%sgrub/splash.xpm.gz\n'
                        % (self.grubbyPartitionName(bootDevs[0]), cfPath))
                f.write("hiddenmenu\n")

            
        if self.password:
            f.write('password --md5 %s\n' %(self.password))
        
        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

            initrd = self.makeInitrd(kernelTag, instRoot)

            f.write('title %s (%s)\n' % (longlabel, version))
            f.write('\troot %s\n' % self.grubbyPartitionName(bootDevs[0]))

            realroot = " root=%s" % rootDev.fstabSpec

            if version.endswith("xen0") or (version.endswith("xen") and not os.path.exists("/proc/xen")):
                # hypervisor case
                sermap = { "ttyS0": "com1", "ttyS1": "com2",
                           "ttyS2": "com3", "ttyS3": "com4" }
                if self.serial and sermap.has_key(self.serialDevice) and \
                       self.serialOptions:
                    hvs = "%s=%s" %(sermap[self.serialDevice],
                                    self.serialOptions)
                else:
                    hvs = ""
                if version.endswith("xen0"):
                    hvFile = "%sxen.gz-%s %s" %(cfPath,
                                                version.replace("xen0", ""),
                                                hvs)
                else:
                    hvFile = "%sxen.gz-%s %s" %(cfPath,
                                                version.replace("xen", ""),
                                                hvs)
                f.write('\tkernel %s\n' %(hvFile,))
                f.write('\tmodule %s ro%s' %(kernelFile, realroot))
                if self.args.get():
                    f.write(' %s' % self.args.get())
                f.write('\n')

                if initrd:
                    f.write('\tmodule %s%s\n' % (cfPath, initrd))
            else: # normal kernel
                f.write('\tkernel %s ro%s' % (kernelFile, realroot))
                if self.args.get():
                    f.write(' %s' % self.args.get())
                f.write('\n')

                if initrd:
                    f.write('\tinitrd %s%s\n' % (cfPath, initrd))

        for (label, longlabel, device) in chainList:
            if ((not longlabel) or (longlabel == "")):
                continue
            f.write('title %s\n' % (longlabel))
            f.write('\trootnoverify %s\n' % self.grubbyPartitionName(device))
#            f.write('\tmakeactive\n')
            f.write('\tchainloader +1')
            f.write('\n')

        f.close()

        if not "/efi/" in cf:
            os.chmod(cf, self.perms)

        try:
            # make symlink for menu.lst (default config file name)
            menulst = "%s%s/menu.lst" % (instRoot, self.configdir)
            if os.access (menulst, os.R_OK):
                os.rename(menulst, menulst + ".rpmsave")
            os.symlink("./grub.conf", menulst)
        except:
            pass

        try:
            # make symlink for /etc/grub.conf (config files belong in /etc)
            etcgrub = "%s%s" % (instRoot, "/etc/grub.conf")
            if os.access (etcgrub, os.R_OK):
                os.rename(etcgrub, etcgrub + ".rpmsave")
            os.symlink(".." + self.configfile, etcgrub)
        except:
            pass

    def writeDeviceMap(self, instRoot, usedDevs, upgrade=False):

        if os.access(instRoot + "/boot/grub/device.map", os.R_OK):
            # For upgrade, we want also e.g. devs that has been added
            # to file during install for chainloading.
            if upgrade:
                f = open(instRoot + "/boot/grub/device.map", "r")
                for line in f:
                    if line.startswith('(hd'):
                        (grubdisk, dev) = line.split()[:2]
                        dev = dev[5:]
                        if dev in self.drivelist:
                            usedDevs.add(dev)
                f.close()
            os.rename(instRoot + "/boot/grub/device.map",
                      instRoot + "/boot/grub/device.map.rpmsave")

        f = open(instRoot + "/boot/grub/device.map", "w+")
        f.write("# this device map was generated by anaconda\n")
        usedDiskDevs = set()
        for dev in usedDevs:
            drive = getDiskPart(dev, self.storage)[0]
            usedDiskDevs.add(drive)
        devs = list(usedDiskDevs)
        devs.sort()
        for drive in devs:
            # XXX hack city.  If they're not the sort of thing that'll
            # be in the device map, they shouldn't still be in the list.
            dev = self.storage.devicetree.getDeviceByName(drive)
            if not dev.type == "mdarray":
                f.write("(%s)     %s\n" % (self.grubbyDiskName(drive), dev.path))
        f.close()

    def writeSysconfig(self, instRoot, grubTarget, upgrade):
        sysconf = '/etc/sysconfig/grub'
        if os.access (instRoot + sysconf, os.R_OK):
            if upgrade:
                return
            self.perms = os.stat(instRoot + sysconf)[0] & 0777
            os.rename(instRoot + sysconf,
                      instRoot + sysconf + '.rpmsave')
        # if it's an absolute symlink, just get it out of our way
        elif (os.path.islink(instRoot + sysconf) and
              os.readlink(instRoot + sysconf)[0] == '/'):
            if upgrade:
                return
            os.rename(instRoot + sysconf,
                      instRoot + sysconf + '.rpmsave')
        f = open(instRoot + sysconf, 'w+')
        f.write("boot=/dev/%s\n" %(grubTarget,))
        f.write("forcelba=0\n")
        f.close()

    def grubbyDiskName(self, name):
        return "hd%d" % self.drivelist.index(name)

    def grubbyPartitionName(self, dev):
        (name, partNum) = getDiskPart(dev, self.storage)
        if partNum != None:
            return "(%s,%d)" % (self.grubbyDiskName(name), partNum)
        else:
            return "(%s)" %(self.grubbyDiskName(name))
    

    def getBootloaderConfig(self, instRoot, bl, kernelList,
                            chainList, defaultDev):
        config = bootloaderInfo.getBootloaderConfig(self, instRoot,
                                                    bl, kernelList, chainList,
                                                    defaultDev)

        liloTarget = bl.getDevice()

        config.addEntry("boot", '/dev/' + liloTarget, replace = 0)
        config.addEntry("map", "/boot/map", replace = 0)
        config.addEntry("install", "/boot/boot.b", replace = 0)
        message = "/boot/message"

        if self.pure is not None and not self.useGrubVal:
            config.addEntry("restricted", replace = 0)
            config.addEntry("password", self.pure, replace = 0)

        if self.serial == 1:
           # grab the 0-based number of the serial console device
            unit = self.serialDevice[-1]
            # FIXME: we should probably put some options, but lilo
            # only supports up to 9600 baud so just use the defaults
            # it's better than nothing :(
            config.addEntry("serial=%s" %(unit,))
        else:
            # message screws up serial console
            if os.access(instRoot + message, os.R_OK):
                config.addEntry("message", message, replace = 0)

        if not config.testEntry('lba32'):
            if bl.above1024 and not iutil.isX86(bits=32):
                config.addEntry("lba32", replace = 0)

        return config

    def write(self, instRoot, bl, kernelList, chainList,
              defaultDev):
        if self.timeout is None and chainList:
            self.timeout = 5

        # XXX HACK ALERT - see declaration above
        if self.doUpgradeOnly:
            if self.useGrubVal:
                return self.writeGrub(instRoot, bl, kernelList,
                                      chainList, defaultDev,
                                      upgrade = True)
            return 0

        if len(kernelList) < 1:
            raise BootyNoKernelWarning

        rc = self.writeGrub(instRoot, bl, kernelList, 
                            chainList, defaultDev,
                            not self.useGrubVal)
        if rc:
            return rc

        # XXX move the lilo.conf out of the way if they're using GRUB
        # so that /sbin/installkernel does a more correct thing
        if self.useGrubVal and os.access(instRoot + '/etc/lilo.conf', os.R_OK):
            os.rename(instRoot + "/etc/lilo.conf",
                      instRoot + "/etc/lilo.conf.anaconda")

        return 0

    def getArgList(self):
        args = bootloaderInfo.getArgList(self)

        if self.password:
            args.append("--md5pass=%s" %(self.password))

        return args

    def __init__(self, anaconda):
        bootloaderInfo.__init__(self, anaconda)

        # these have to be set /before/ efiBootloaderInfo.__init__(), or
        # they'll be overwritten.
        self._configdir = "/boot/grub"
        self._configname = "grub.conf"

        efiBootloaderInfo.__init__(self, anaconda, initialize=False)

        # XXX use checkbootloader to determine what to default to
        self.useGrubVal = 1
        self.kernelLocation = "/boot/"
        self.password = None
        self.pure = None
