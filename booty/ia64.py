from booty import BootyNoKernelWarning
from bootloaderInfo import *

class ia64BootloaderInfo(efiBootloaderInfo):
    def getBootloaderConfig(self, instRoot, bl, kernelList,
                            chainList, defaultDev):
        config = bootloaderInfo.getBootloaderConfig(self, instRoot,
                                                    bl, kernelList, chainList,
                                                    defaultDev)
        # altix boxes need relocatable (#120851)
        config.addEntry("relocatable")

        return config

    def writeLilo(self, instRoot, bl, kernelList, 
                  chainList, defaultDev):
        config = self.getBootloaderConfig(instRoot, bl,
                                          kernelList, chainList, defaultDev)
        return config.write(instRoot + self.configfile, perms = 0755)

    def write(self, instRoot, bl, kernelList, chainList, defaultDev):
        if len(kernelList) >= 1:
            rc = self.writeLilo(instRoot, bl, kernelList,
                                chainList, defaultDev)
            if rc:
                return rc
        else:
            raise BootyNoKernelWarning

        rc = self.removeOldEfiEntries(instRoot)
        if rc:
            return rc
        return self.addNewEfiEntry(instRoot)

    def __init__(self, anaconda):
        efiBootloaderInfo.__init__(self, anaconda)
        self._configname = "elilo.conf"
        self._bootloader = "elilo.efi"
