import rpm
from string import *
import types

class Package:

    def __repr__(self):
	return self.name

    def __init__(self, header):
	self.h = header
	self.name = header[rpm.RPMTAG_NAME]
	self.selected = 0

class Component:

    def __len__(self):
	return len(self.items)

    def __getitem__(self, key):
	return self.items[key]

    def addPackage(self, package):
	self.items.append(package)

    def addInclude(self, component):
	self.includes.append(component)

    def select(self, recurse = 1):
	for n in self.items:
	    n.selected = 1
	if recurse:
	    for n in self.includes:
		n.select(recurse)

    def __init__(self, name, selected, hidden = 0):
	self.name = name
	self.hidden = hidden
	self.selected = selected
	self.items = []
	self.includes = []

class ComponentSet:

    def __len__(self):
	return len(self.comps)

    def __getitem__(self, key):
	if (type(key) == types.IntType):
	    return self.comps[key]
	return self.compsDict[key]

    def selected(self):
	l = []
 	keys = self.packages.keys()
	keys.sort()
	for name in keys:
	    if self.packages[name].selected: l.append(self.packages[name])
	return l

    def readCompsFile(self, arch, filename, packages):
	file = open(filename, "r")
	lines = file.readlines()
	file.close()
	top = lines[0]
	lines = lines[1:]
	if (top != "2\n"):
	    raise TypeError, "comp file version 2 expected"
	
	comp = None
	self.comps = []
	self.compsDict = {}
	for l in lines:
	    l = l[:len(l) - 1]
	    if (not l): continue

	    if (find(l, ":") > -1):
		(archList, l) = split(l, ":", 1)
		while (l[0] == " "): l = l[1:]
		archList = split(archList)
		skip = 1
		for n in archList:
		    if (n == arch): 
			skip = 0
			break
		if (skip): continue

	    if (comp == None):
		(default, l) = split(l, None, 1)
		hidden = 0
		if (l[0:6] == "--hide"):
		    hidden = 1
		    (foo, l) = split(l, None, 1)
		    
		comp = Component(l, default, hidden)
	    elif (l == "end"):
		self.comps.append(comp)
		self.compsDict[comp.name] = comp
		comp = None
	    else:

		if (l[0] == "@"):
		    (at, l) = split(l, None, 1)
		    comp.addInclude(self.compsDict[l])
		else:
		    comp.addPackage(packages[l])

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

    def __init__(self, arch, file, hdlist):
	self.list = []
	self.packages = {}
	for h in hdlist:
	    self.packages[h[rpm.RPMTAG_NAME]] = Package(h)
	self.readCompsFile(arch, file, self.packages)
