import string
import os

class LiloConfiguration:

    def __repr__(self, tab = 0):
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
	for image in self.images:
	    (type, name, cl) = image
	    s = s + "\n%s=%s\n" % (type, name)
	    s = s + cl.__repr__(1)
	return s

    def addEntry(self, item, val = None):
	if not self.items.has_key(item):
	    self.order.append(item)
	if (val):
	    self.items[item] = str(val)
	else:
	    self.items[item] = None

    def addImage (self, type, name, config):
	self.images.append((type, name, config))

    def delImage (self, name):
        for entry in self.images:
            type, label, config = entry
            if label == name:
                self.images.remove (entry)

    def write(self, file):
	f = open(file, "w")
	f.write(self.__repr__())
	f.close()
	os.chmod(file, 0644)

    def read(self, file):
	f = open(file, "r")
	image = None
	for l in f.readlines():
	    l = l[:-1]
	    orig = l
	    while (l and l[0] == ' ' or l[0] == '\t'):
		l = l[1:]
	    if (not l or l[0] == '#'):
		self.order.append('#' + orig)
		continue
	    fields = string.split(l, '=', 1)
	    if (len(fields) == 2):
		if (fields[0] == "image"):
		    image = LiloConfiguration()
		    self.addImage(fields[0], fields[1], image)
		    args = None
		elif (fields[0] == "other"):
		    image = LiloConfiguration()
		    self.addImage(fields[0], fields[1], image)
		    args = None
                else:
		    args = (fields[0], fields[1])
	    else:
		args = (l,)

	    if (args and image):
		apply(image.addEntry, args)
	    elif args:
		apply(self.addEntry, args)
	    
	f.close()

    def __init__(self):
	self.order = []
	self.images = []		# more (type, name, LiloConfiguration) pair
	self.items = {}

if __name__ == "__main__":
    config = LiloConfiguration ()
    config.read ('lilo.conf')
    print config
    config.delImage ('/boot/vmlinuz-2.2.5-15')
    print '----------------------------------'
    print config
    config.delImage ('/dev/hda3')
    print '----------------------------------'    
    print config
    

