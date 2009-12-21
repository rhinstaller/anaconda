import os
import iutil

from booty import BootyNoKernelWarning
from bootloaderInfo import *
from util import getDiskPart

class alphaBootloaderInfo(bootloaderInfo):
    def wholeDevice (self, path):
        (device, foo) = getDiskPart(path, self.storage)
        return device

    def partitionNum (self, path):
        # getDiskPart returns part numbers 0-based; we need it one based
        # *sigh*
        (foo, partitionNumber) = getDiskPart(path, self.storage)
        return partitionNumber + 1

    def writeAboot(self, instRoot, bl, kernelList,
                   chainList, defaultDev):
        rootDevice = self.storage.rootDevice
        try:
            bootDevice = self.storage.mountpoints["/boot"]
        except KeyError:
            bootDevice = rootDevice

        bootnotroot = bootDevice != rootDevice

        confFile = instRoot + self.configfile

        # If /etc/aboot.conf already exists we rename it
        # /etc/aboot.conf.rpmsave.
        if os.path.isfile(confFile):
            os.rename (confFile, confFile + ".rpmsave")

        # Then we create the necessary files. If the root device isn't
        # the boot device, we create /boot/etc/ where the aboot.conf
        # will live, and we create /etc/aboot.conf as a symlink to it.
        if bootnotroot:
            # Do we have /boot/etc ? If not, create one
            if not os.path.isdir (instRoot + '/boot/etc'):
                os.mkdir(instRoot + '/boot/etc', 0755)

            # We install the symlink (/etc/aboot.conf has already been
            # renamed in necessary.)
            os.symlink("../boot" + self.configfile, confFile)

            cfPath = instRoot + "/boot" + self.configfile
            # Kernel path is set to / because a boot partition will
            # be a root on its own.
            kernelPath = '/'
        # Otherwise, we just need to create /etc/aboot.conf.
        else:
            cfPath = confFile
            kernelPath = self.kernelLocation

        # If we already have an aboot.conf, rename it
        if os.access (cfPath, os.R_OK):
            self.perms = os.stat(cfPath)[0] & 0777
            os.rename(cfPath, cfPath + '.rpmsave')
                
        # Now we're going to create and populate cfPath.
        f = open (cfPath, 'w+')
        f.write ("# aboot default configurations\n")

        if bootnotroot:
            f.write ("# NOTICE: You have a /boot partition. This means that\n")
            f.write ("#         all kernel paths are relative to /boot/\n")

        # bpn is the boot partition number.
        bpn = self.partitionNum(bootDevice.path)
        lines = 0

        # We write entries line using the following format:
        # <line><bpn><kernel-name> root=<rootdev> [options]
        # We get all the kernels we need to know about in kernelList.

        for (kernel, tag, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" %(kernelPath, kernelTag)

            f.write("%d:%d%s" %(lines, bpn, kernelFile))

            # See if we can come up with an initrd argument that exists
            initrd = self.makeInitrd(kernelTag, instRoot)
            if initrd:
                f.write(" initrd=%s%s" %(kernelPath, initrd))

            realroot = rootDevice.fstabSpec
            f.write(" root=%s" %(realroot,))

            args = self.args.get()
            if args:
                f.write(" %s" %(args,))

            f.write("\n")
            lines = lines + 1

        # We're done writing the file
        f.close ()
        del f

        # Now we're ready to write the relevant boot information. wbd
        # is the whole boot device, bdpn is the boot device partition
        # number.
        wbd = self.wholeDevice (bootDevice.path)
        bdpn = self.partitionNum (bootDevice.path)

        # Calling swriteboot. The first argument is the disk to write
        # to and the second argument is a path to the bootstrap loader
        # file.
        args = [("/dev/%s" % wbd), "/boot/bootlx"]
        rc = iutil.execWithRedirect ('/sbin/swriteboot', args,
                                     root = instRoot,
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5")
        if rc:
            return rc

        # Calling abootconf to configure the installed aboot. The
        # first argument is the disk to use, the second argument is
        # the number of the partition on which aboot.conf resides.
        # It's always the boot partition whether it's / or /boot (with
        # the mount point being omitted.)
        args = [("/dev/%s" % wbd), str (bdpn)]
        rc = iutil.execWithRedirect ('/sbin/abootconf', args,
                                     root = instRoot,
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5")
        if rc:
            return rc

        return 0


    def write(self, instRoot, bl, kernelList, chainList, defaultDev):
        if len(kernelList) < 1:
            raise BootyNoKernelWarning

        return self.writeAboot(instRoot, bl, kernelList,
                               chainList, defaultDev)

    def __init__(self, anaconda):
        bootloaderInfo.__init__(self, anaconda)
        self.useGrubVal = 0
        self._configdir = "/etc"
        self._configname = "aboot.conf"
        # self.kernelLocation is already set to what we need.
        self.password = None
        self.pure = None
