import string
import os

def needsEnterpriseKernel():
    rc = 0

    try:
        f = open("/proc/e820info", "r")
    except IOError:
        return 0
    for l in f.readlines():
	l = string.split(l)
	if l[3] == '(reserved)': continue

	regionEnd = (string.atol(l[0], 16) - 1) + string.atol(l[2], 16)
	if regionEnd > 0xffffffffL:
	    rc = 1

    return rc

class LiloConfigFile:
    def __repr__ (self, tab = 0):
	s = ""
	for n in self.order:
	    if (tab):
		s = s + '\t'
	    if n[0] == '#':
		s = s + n[1:]
	    else:
		s = s + n
		if self.items[n]:
		    s = s + "=" + self.items[n]
	    s = s + '\n'
	for cl in self.images:
	    s = s + "\n%s=%s\n" % (cl.imageType, cl.path)
	    s = s + cl.__repr__(1)
	return s

    def addEntry(self, item, val = None, replace = 1):
	if not self.items.has_key(item):
	    self.order.append(item)
	elif not replace:
	    return

	if (val):
	    self.items[item] = str(val)
	else:
	    self.items[item] = None

    def getEntry(self, item):
	return self.items[item]

    def delEntry(self, item):
	newOrder = []
	for i in self.order:
	    if item != i: newOrder.append(i)
	self.order = newOrder

	del self.items[item]

    def testEntry(self, item):
        if self.items.has_key(item):
            return 1
        else:
            return 0

    def getImage(self, label):
        for config in self.images:
	    if config.getEntry('label') == label:
		return (config.imageType, config)

	raise IndexError, "unknown image %s" % (label,)

    def addImage (self, config):
	# make sure the config has a valid label
	config.getEntry('label')
	if not config.path or not config.imageType:
	    raise ValueError, "subconfig missing path or image type"

	self.images.append(config)

    def delImage (self, label):
        for config in self.images:
	    if config.getEntry('label') == label:
                self.images.remove (config)
		return

	raise IndexError, "unknown image %s" % (label,)

    def listImages (self):
	l = []
        for config in self.images:
	    l.append(config.getEntry('label'))
	return l

    def getPath (self):
	return self.path

    def write(self, file, perms = 0644):
	f = open(file, "w")
	f.write(self.__repr__())
	f.close()
	os.chmod(file, perms)

    def read (self, file):
	f = open(file, "r")
	image = None
	for l in f.readlines():
	    l = l[:-1]
	    orig = l
	    while (l and (l[0] == ' ' or l[0] == '\t')):
		l = l[1:]
	    if not l:
		continue
	    if l[0] == '#':
		self.order.append('#' + orig)
		continue
	    fields = string.split(l, '=', 1)
	    if (len(fields) == 2):
		f0 = string.strip (fields [0])
		f1 = string.strip (fields [1])
		if (f0 == "image" or f0 == "other"):
		    if image: self.addImage(image)
		    image = LiloConfigFile(imageType = f0, 
					   path = f1)
		    args = None
                else:
		    args = (f0, f1)
	    else:
		args = (string.strip (l),)

	    if (args and image):
		apply(image.addEntry, args)
	    elif args:
		apply(self.addEntry, args)

	if image: self.addImage(image)
	    
	f.close()

    def __init__(self, imageType = None, path = None):
	self.imageType = imageType
	self.path = path
	self.order = []
	self.images = []
	self.items = {}
