import rpm
from string import *
import types
import iutil
import urllib

class Package:

    def __getitem__(self, item):
	return self.h[item]

    def __repr__(self):
	return self.name

    def __init__(self, header):
	self.h = header
	self.name = header[rpm.RPMTAG_NAME]
	self.selected = 0

class HeaderList:

    def selected(self):
	l = []
 	keys = self.packages.keys()
	keys.sort()
	for name in keys:
	    if self.packages[name].selected: l.append(self.packages[name])
	return l

    def has_key(self, item):
	return self.packages.has_key(item)

    def keys(self):
        return self.packages.keys()

    def __getitem__(self, item):
	return self.packages[item]

    def __init__(self, hdlist):
        self.hdlist = hdlist
	self.packages = {}
	for h in hdlist:
	    name = h[rpm.RPMTAG_NAME]
	    score1 = rpm.archscore(h['arch'])
	    if (score1):
		if self.packages.has_key(name):
		    score2 = rpm.archscore(self.packages[name].h['arch'])
		    if (score1 < score2):
			self.packages[name] = Package(h)
		else:
		    self.packages[name] = Package(h)

class HeaderListFromFile (HeaderList):

    def __init__(self, path):
	hdlist = rpm.readHeaderListFromFile(path)
	HeaderList.__init__(self, hdlist)

class HeaderListFD (HeaderList):
    def __init__(self, fd):
	hdlist = rpm.readHeaderListFromFD (fd)
	HeaderList.__init__(self, hdlist)

class Component:

    def __len__(self):
	return len(self.items)

    def __getitem__(self, key):
	return self.items[key]

    def addPackage(self, package):
	self.items[package] = package

    def addInclude(self, component):
	self.includes.append(component)
	
    def addRequires(self, component):
	self.requires = component

    def select(self, recurse = 1):
        self.selected = 1
	for n in self.items.keys ():
	    self.items[n].selected = 1
	if recurse:
	    for n in self.includes:
		if n.requires:
		    if n.requires.selected:
			n.select(recurse)
	        else:
		    n.select(recurse)
		if n.requires:
		    if n.requires.selected:
			n.select(recurse)
	        else:
		    n.select(recurse)

    def unselect(self, recurse = 1):
        self.selected = 0
	for n in self.items.keys ():
	    self.items[n].selected = 0
	if recurse:
	    for n in self.includes:
		n.unselect(recurse)

    def __init__(self, name, selected, hidden = 0):
	self.name = name
	self.hidden = hidden
	self.selected = selected
	self.items = {}
	self.requires = None
	self.includes = []

class ComponentSet:

    def __len__(self):
	return len(self.comps)

    def __getitem__(self, key):
	if (type(key) == types.IntType):
	    return self.comps[key]
	return self.compsDict[key]

    def keys(self):
	return self.compsDict.keys()

    def readCompsFile(self, filename, packages):
	arch = iutil.getArch()
	file = urllib.urlopen(filename)
	lines = file.readlines()

	file.close()
	top = lines[0]
	lines = lines[1:]
	if (top != "2.1\n" and top != "2\n" and top != "0.1\n"):
	    raise TypeError, "comp file version 2.1 expected"
	
	comp = None
	self.comps = []
	self.compsDict = {}
	for l in lines:
	    l = l[:len(l) - 1]
	    if (not l): continue

	    if (find(l, ":") > -1):
		(archList, l) = split(l, ":", 1)
		while (l[0] == " "): l = l[1:]

		skipIfFound = 0
		if (archList[0] == '!'):
		    skipIfFound = 1
		    archList = archList[1:]
		archList = split(archList)
		found = 0
		for n in archList:
		    if (n == arch): 
			found = 1
			break
		if ((found and skipIfFound) or 
				(not found and not skipIfFound)):
		    continue
	    
	    if (comp == None):
		(default, l) = split(l, None, 1)
		hidden = 0
		if (l[0:6] == "--hide"):
		    hidden = 1
		    (foo, l) = split(l, None, 1)
                if l == "Base":
                    hidden = 1
		comp = Component(l, default == '1', hidden)
	    elif (l == "end"):
		self.comps.append(comp)
		self.compsDict[comp.name] = comp
		comp = None
	    else:
		if (l[0] == "@"):
		    (at, l) = split(l, None, 1)
		    comp.addInclude(self.compsDict[l])
		elif (find(l, "?") > -1):
		    (reqComp, l) = split(l, "?", 1)
		    reqComp = reqComp[:-1]
		    while (l[0] == " "): l = l[1:]
		    comp.addInclude(self.compsDict[l])
		    self.compsDict[l].addRequires(self.compsDict[reqComp])
		else:
		    comp.addPackage(packages[l])
                    
        everything = Component("Everything", 0, 0)
        for package in packages.keys ():
            everything.addPackage (packages[package])
        self.comps.append (everything)


    def __repr__(self):
	s = ""
	for n in self.comps:
	    s = s + "{ " + n.name + " [";
	    for include in n.includes:
		s = s + " @" + include.name
		
	    for package in n:
		s = s + " " + package
	    s = s + " ] } "
	    
	return s

    def __init__(self, file, hdlist):
	self.list = []
	self.packages = hdlist
	self.readCompsFile(file, self.packages)
