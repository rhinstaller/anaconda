import os
from lilo import LiloConfigFile
import isys
import iutil
import rpm

class EliloConfiguration:

    def setEliloImages(self, images):
	self.eliloImages = images

    def getEliloImages(self, fstab):
	for (mntpoint, device, fsystem, doFormat, size) in \
		    fstab.mountList():

	    if mntpoint == '/':
		self.eliloImages[device] = ("linux", 2)
		self.default = "linux"

	return (self.eliloImages, self.default)

    def install(self, fstab, instRoot, hdList, upgrade):
	# If the root partition is on a loopback device, lilo won't work!
	if fstab.rootOnLoop():
	    return 

	if not self.eliloImages:
	    (images, default) = self.getEliloImages(fstab)
	    self.setEliloImages(images)

        # on upgrade read in the elilo config file
	elilo = LiloConfigFile ()
	perms = 0644
        if os.access (instRoot + '/boot/efi/elilo.conf', os.R_OK):
	    perms = os.stat(instRoot + '/boot/efi/elilo.conf')[0] & 0777
	    #elilo.read (instRoot + '/boot/efi/elilo.conf')
	    os.rename(instRoot + '/boot/efi/elilo.conf',
		      instRoot + '/boot/efi/elilo.conf.rpmsave')

	# Remove any invalid entries that are in the file; we probably
	# just removed those kernels. 
	for label in elilo.listImages():
	    (fsType, sl) = elilo.getImage(label)
	    if fsType == "other": continue

	    if not os.access(instRoot + sl.getPath(), os.R_OK):
		elilo.delImage(label)

	bootpart = fstab.getBootDevice()
	boothd = fstab.getMbrDevice()

	elilo.addEntry("timeout", "50", replace = 0)

	smpInstalled = (hdList.has_key('kernel-smp') and 
                        hdList['kernel-smp'].selected)

        rootDev = fstab.getRootDevice ()
        if rootDev:
	    # strip off the filesystem; we don't need it
            rootDev = rootDev[0]
        else:
            raise RuntimeError, "Installing lilo, but there is no root device"

        kernelList = []
        otherList = []

        main = self.default

        for (drive, (label, eliloType)) in self.eliloImages.items ():
            if (drive == rootDev) and label:
                main = label
            elif label:
                otherList.append (label, "/dev/" + drive)

	label = main

	label = main
	if (smpInstalled):
	    kernelList.append((main, hdList['kernel-smp'], "smp"))
	    label = main + "-up"

	kernelList.append((label, hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    kernelTag = "-%s-%s%s" % (kernel[rpm.RPMTAG_VERSION],
                                      kernel[rpm.RPMTAG_RELEASE], tag)
	    kernelFile = "vmlinuz" + kernelTag

	    try:
		(fsType, sl) = elilo.getImage(label)
		elilo.delImage(label)
	    except IndexError, msg:
		sl = LiloConfigFile(imageType = "image", path = kernelFile)
		
	    initrd = self.makeInitrd (kernelTag, instRoot)

	    sl.addEntry("label", label)
	    if os.access (instRoot + "/boot/efi/" + initrd, os.R_OK):
		sl.addEntry("initrd", initrd)
		
	    sl.addEntry("read-only")
	    sl.addEntry("root", '/dev/' + rootDev)

	    if self.eliloAppend:
		sl.addEntry('append', '"%s"' % (self.eliloAppend,))
		
	    elilo.addImage (sl)

	elilo.write(instRoot + "/boot/efi/elilo.conf", perms = perms)
	
    def makeInitrd (self, kernelTag, instRoot):
	initrd = "initrd%s.img" % (kernelTag, )
	if not self.initrdsMade.has_key(initrd):
	    iutil.execWithRedirect("/sbin/mkinitrd",
	    			[ "/sbin/mkinitrd",
				"--ifneeded",
				"/boot/efi/%s" % initrd,
				kernelTag[1:] ],
				stdout = None, stderr = None, searchPath = 1,
				root = instRoot)
	    self.initrdsMade[kernelTag] = 1
	return initrd

    def __init__(self):
	self.eliloImages = {}
	self.initrdsMade = {}
	self.eliloAppend = None
	self.default = None

if __name__ == "__main__":
    config = LiloConfigFile ()
    config.read ('/boot/efi/elilo.conf')
    print config
    print "image list", config.listImages()
    config.delImage ('vmlinuz-2.4.0-0.32')
    print '----------------------------------'
    config = LiloConfigFile ()
    config.read ('/boot/efi/elilo.conf')
    print config
    print '----------------------------------'    
    print config.getImage('vmlinuz-2.4.0-0.32')
    

