# For an install to proceed, the following todo fields must be filled in
#
#	mount list via addMount()		(unless todo.runLive)

import rpm, os

def instCallback(what, amount, total, key, data):
    if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
	(h, method) = key
	data.setPackage(h[rpm.RPMTAG_NAME])
	data.setPackageScale(0, 1)
	fn = method.getFilename(h)
	d = os.open(fn, os.O_RDONLY)
	return d
    elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	data.setPackageScale(amount, total)


class ToDo:

    def installSystem(self):
	# make sure we have the header list and comps file
	self.headerList()
	comps = self.compsList()

	os.mkdir(self.instPath + '/var')
	os.mkdir(self.instPath + '/var/lib')
	os.mkdir(self.instPath + '/var/lib/rpm')

	db = rpm.opendb(1, self.instPath)
	ts = rpm.TransactionSet(self.instPath, db)

	for p in comps.selected():
	    ts.add(p.h, (p.h, self.method))

	ts.order()
	p = self.intf.packageProgessWindow()
	ts.run(0, 0, instCallback, p)

    def addMount(self, device, location):
	self.mounts.append((device, location))

    def freeHeaders(self):
	if (self.hdList):
	    self.hdList = None

    def headerList(self):
	if (not self.hdList):
	    w = self.intf.waitWindow("Reading", 
			"Reading package information...")
	    self.hdList = self.method.readHeaders()
	    w.pop()
	return self.hdList

    def compsList(self):
	if (not self.comps):
	    self.headerList()
	    self.comps = self.method.readComps(self.hdList)
	self.comps['Base'].select(1)
	return self.comps

    def __init__(self, intf, method, rootPath, runLive):
	self.intf = intf
	self.method = method
	self.mounts = []
	self.hdList = None
	self.comps = None
	self.instPath = rootPath
	self.runLive = runLive
	pass
