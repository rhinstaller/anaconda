import os
from lilo import LiloConfigFile
import isys
import iutil

class EliConfiguration:

    def setEliImages(self, images):
	self.eliImages = images

    def getEliImages(self, fstab):
	for (mntpoint, device, fsystem, doFormat, size) in \
		    fstab.mountList():

	    if mntpoint == '/':
		self.eliImages[device] = ("linux", 2)
		self.default = "linux"

	return (self.eliImages, self.default)

    def install(self, fstab, instRoot, hdList, upgrade):
	# If the root partition is on a loopback device, lilo won't work!
	if fstab.rootOnLoop():
	    return 

	if not self.eliImages:
	    (images, default) = self.getEliImages(fstab)
	    self.setEliImages(images)

        # on upgrade read in the eli config file
	eli = LiloConfigFile ()
	perms = 0644
        if os.access (instRoot + '/boot/eli.cfg', os.R_OK):
	    perms = os.stat(instRoot + '/boot/eli.conf')[0] & 0777
	    #lilo.read (instRoot + '/boot/eli.cfg')
	    os.rename(instRoot + '/boot/eli.cfg',
		      instRoot + '/boot/eli.cfg.rpmsave')

	# Remove any invalid entries that are in the file; we probably
	# just removed those kernels. 
	for label in lilo.listImages():
	    (fsType, sl) = lilo.getImage(label)
	    if fsType == "other": continue

	    if not os.access(instRoot + sl.getPath(), os.R_OK):
		lilo.delImage(label)

	bootpart = fstab.getBootDevice()
	boothd = fstab.getMbrDevice()

	eli.addEntry("timeout", "50", replace = 0)

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

        for (drive, (label, eliType)) in self.eliImages.items ():
            if (drive == rootDev) and label:
                main = label
            elif label:
                otherList.append (label, "/dev/" + drive)

        eli.addEntry("default", self.default)        

	label = main

	label = main
	if (smpInstalled):
	    kernelList.append((main, hdList['kernel-smp'], "smp"))
	    label = main + "-up"

	kernelList.append((label, hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    kernelTag = "-%s-%s%s" % (kernel['version'], kernel['release'], tag)
	    kernelFile = "/boot/vmlinuz" + kernelTag

	    try:
		(fsType, sl) = lilo.getImage(label)
		lilo.delImage(label)
	    except IndexError, msg:
		sl = LiloConfigFile(imageType = "image", path = kernelFile)

	    initrd = self.makeInitrd (kernelTag, instRoot)

	    sl.addEntry("label", label)
	    if os.access (instRoot + initrd, os.R_OK):
		sl.addEntry("initrd", initrd)

	    sl.addEntry("read-only")
	    sl.addEntry("root", '/dev/' + rootDev)

	    if self.eliAppend:
		sl.addEntry('append', '"%s"' % (self.eliAppend,))
		
	    eli.addImage ("image", kernelFile, sl)
	    lilo.addImage (sl)

	eli.write(instRoot + "/boot/eli.cfg", perms = perms)

    def __init__(self):
	self.eliImages = {}
	self.eliAppend = None
	self.default = None

if __name__ == "__main__":
    config = LiloConfigFile ()
    config.read ('/etc/lilo.conf')
    print config
    print "image list", config.listImages()
    config.delImage ('/boot/vmlinuz-2.2.5-15')
    print '----------------------------------'
    config = LiloConfigFile ()
    config.read ('/etc/lilo.conf')
    print config
    print '----------------------------------'    
    print config.getImage('/boot/vmlinuz-2.2.5-15')
    

