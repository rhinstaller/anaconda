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
	# just removed those kernels. While we're here, build an index
	# to the already-configured (and valid) eli images by the eli
	# label, as we can normally only get them by filename which isn't
	# easily done.
	imagesByLabel = {}
	for image in eli.listImages():
	    (fsType, sl) = eli.getImage(image)
	    if fsType == "other": continue
	    if not os.access(instRoot + image, os.R_OK):
		eli.delImage(image)
	    else:
		imagesByLabel[sl.getEntry('label')] = image

	bootpart = fstab.getBootDevice()
	boothd = fstab.getMbrDevice()

	eli.addEntry("timeout", "50", replace = 0)

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

	kernelList.append((label, hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    if imagesByLabel.has_key(label):
		(fsType, sl) = eli.getImage(imagesByLabel[label])
		eli.delImage(imagesByLabel[label])
	    else:
		sl = LiloConfigFile()

	    kernelTag = "-%s-%s%s" % (kernel['version'], kernel['release'], tag)
	    kernelFile = "/boot/vmlinuz" + kernelTag

	    sl.addEntry("label", label)
	    sl.addEntry("read-only")
	    sl.addEntry("root", '/dev/' + rootDev)

	    if self.eliAppend:
		sl.addEntry('append', '"%s"' % (self.eliAppend,))
		
	    eli.addImage ("image", kernelFile, sl)

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
    

